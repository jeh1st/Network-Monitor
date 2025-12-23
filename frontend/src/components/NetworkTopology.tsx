import { useCallback, useEffect, useState, useRef } from 'react';
import ReactFlow, {
    Controls,
    Background,
    useNodesState,
    useEdgesState,
    addEdge
} from 'reactflow';
import type { Node, Edge, Connection } from 'reactflow';
import 'reactflow/dist/style.css';
import DeviceNode from './DeviceNode';

interface NetworkTopologyProps {
    initialNodes: Node[];
    initialEdges: Edge[];
    isInteractive?: boolean;
    onLayoutChange?: (nodes: Node[], edges: Edge[]) => void;
}

const nodeTypes = {
    deviceNode: DeviceNode,
};

const NetworkTopologyApi = ({ initialNodes, initialEdges, isInteractive, onLayoutChange }: NetworkTopologyProps) => {
    const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
    const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

    // Ref to hold current edges to break dependency cycles in callbacks
    const edgesRef = useRef(edges);
    useEffect(() => {
        edgesRef.current = edges;
    }, [edges]);

    // Callback for wireless toggle
    const onWirelessToggle = useCallback((nodeId: string, isWireless: boolean) => {
        // 1. Update Edge visually
        setEdges((eds) => eds.map(e => {
            if (e.target === nodeId) {
                return {
                    ...e,
                    style: { ...e.style, strokeDasharray: isWireless ? '5,5' : '0' },
                    animated: isWireless
                };
            }
            return e;
        }));

        // 2. Persist state in Node Data so it survives disconnection
        setNodes((nds) => nds.map(n => {
            if (n.id === nodeId) {
                return { ...n, data: { ...n.data, isWireless } };
            }
            return n;
        }));
    }, [setEdges, setNodes]);

    // Callback to toggle visibility of children
    const onToggleChildren = useCallback((nodeId: string) => {
        setNodes((currentNodes) => {
            const currentEdges = edgesRef.current; // Read from ref to avoid dependency

            // 1. Find all edges where source is nodeId
            const childEdges = currentEdges.filter(e => e.source === nodeId);
            const childIds = childEdges.map(e => e.target);

            if (childIds.length === 0) return currentNodes;

            // Determine target state (hidden or visible) based on first child
            // If first child is visible (hidden=false/undefined), we want to HIDE.
            // If first child is hidden, we want to SHOW.
            const firstChild = currentNodes.find(n => n.id === childIds[0]);
            const shouldHide = !firstChild?.hidden;

            // Helper to recursively find descendants
            const getDescendants = (ids: string[], allEdges: Edge[]): string[] => {
                let descendants = [...ids];
                ids.forEach(id => {
                    const children = allEdges.filter(e => e.source === id).map(e => e.target);
                    if (children.length > 0) {
                        descendants = [...descendants, ...getDescendants(children, allEdges)];
                    }
                });
                return descendants;
            };

            const descendants = getDescendants(childIds, currentEdges);
            const nodesToUpdate = new Set(descendants);

            return currentNodes.map(n => {
                if (nodesToUpdate.has(n.id)) {
                    return { ...n, hidden: shouldHide };
                }
                return n;
            });
        });
    }, [setNodes]); // No dependency on edges!

    // Propagate changes to parent for "Save Layout" feature
    useEffect(() => {
        if (onLayoutChange) {
            onLayoutChange(nodes, edges);
        }
    }, [nodes, edges, onLayoutChange]);

    // Sync with props (initialNodes/initialEdges) from backend scan
    useEffect(() => {
        setNodes((nds) => {
            return initialNodes.map((inode) => {
                const existingNode = nds.find((n) => n.id === inode.id);
                // Merge existing position and hidden state
                // Also always inject our callbacks
                return {
                    ...inode,
                    position: existingNode ? existingNode.position : inode.position,
                    hidden: existingNode ? existingNode.hidden : inode.hidden,
                    data: {
                        ...inode.data,
                        isWireless: existingNode ? existingNode.data.isWireless : inode.data.isWireless,
                        onWirelessToggle,
                        onToggleChildren
                    }
                };
            });
        });

        if (initialEdges && initialEdges.length > 0) {
            // We need to preserve styles if we just toggled wireless
            // Solution: Merge styles from existing edges
            setEdges((eds) => {
                if (eds.length === 0) return initialEdges;

                return initialEdges.map(newEdge => {
                    const existingEdge = eds.find(e => e.id === newEdge.id);
                    if (existingEdge) {
                        return {
                            ...newEdge,
                            style: existingEdge.style, // Preserve dashed
                            animated: existingEdge.animated
                        };
                    }
                    return newEdge;
                });
            });
        }
    }, [initialNodes, initialEdges, onWirelessToggle, onToggleChildren]);

    const onConnect = useCallback((params: Connection) => {
        setEdges((eds) => {
            // Check if target node has isWireless flag
            const targetNode = nodes.find(n => n.id === params.target);
            const isWireless = targetNode?.data?.isWireless;

            const newEdge = {
                ...params,
                id: `e${params.source}-${params.target}`,
                style: { strokeDasharray: isWireless ? '5,5' : '0' },
                animated: isWireless
            };

            return addEdge(newEdge, eds);
        });
    }, [setEdges, nodes]);

    // Drag Logic for Attached Hidden Children
    const dragStartRef = useRef<{ id: string, x: number, y: number } | null>(null);

    const onNodeDragStart = useCallback((event: any, node: Node) => {
        dragStartRef.current = { id: node.id, x: node.position.x, y: node.position.y };
    }, []);

    const onNodeDragStop = useCallback((event: any, node: Node) => {
        if (!dragStartRef.current || dragStartRef.current.id !== node.id) return;

        const dx = node.position.x - dragStartRef.current.x;
        const dy = node.position.y - dragStartRef.current.y;

        if (dx === 0 && dy === 0) return;

        setNodes((currentNodes) => {
            const currentEdges = edgesRef.current;

            // Reuse the getDescendants logic (duplicated here for now efficiently inside callback)
            const getDescendants = (ids: string[], allEdges: Edge[]): string[] => {
                let descendants = [...ids];
                ids.forEach(id => {
                    const children = allEdges.filter(e => e.source === id).map(e => e.target);
                    if (children.length > 0) {
                        descendants = [...descendants, ...getDescendants(children, allEdges)];
                    }
                });
                return descendants;
            };

            const childEdges = currentEdges.filter(e => e.source === node.id);
            const childIds = childEdges.map(e => e.target);
            const descendants = getDescendants(childIds, currentEdges);
            const nodesToUpdate = new Set(descendants);

            return currentNodes.map(n => {
                // Only move HIDDEN descendants
                if (nodesToUpdate.has(n.id) && n.hidden) {
                    return {
                        ...n,
                        position: {
                            x: n.position.x + dx,
                            y: n.position.y + dy
                        }
                    };
                }
                return n;
            });
        });

        dragStartRef.current = null;
    }, [setNodes]);

    return (
        <div style={{ height: '100%', width: '100%' }}>
            <ReactFlow
                nodes={nodes}
                edges={edges}
                nodeTypes={nodeTypes}
                onNodesChange={onNodesChange}
                onEdgesChange={onEdgesChange}
                onConnect={isInteractive ? onConnect : undefined}
                onEdgesDelete={isInteractive ? (deleted) => setEdges((eds) => eds.filter((e) => !deleted.some((d) => d.id === e.id))) : undefined}
                onNodeDragStart={onNodeDragStart}
                onNodeDragStop={onNodeDragStop}
                nodesDraggable={true}
                nodesConnectable={isInteractive}
                elementsSelectable={true}
                fitView
            >
                <Background color="#aaa" gap={16} />
                <Controls />
            </ReactFlow>
        </div>
    );
};

export default NetworkTopologyApi;
