#!/usr/bin/env python3

import networkx as nx

class ComponentsGraph :
    """
    Components graph for checking if tree and retrieving paths
    """
    
    def __init__( self, data_connections : dict) -> None :
        self.graph_sides   = data_connections['sides']
        self.graph_bridges = data_connections['bridges']
        self.graph         = nx.Graph()
        
        for side in data_connections['edges'] :
            for edge in data_connections['edges'][side] :
                self.graph.add_edge( edge[0], edge[1])
        
        return
    
    def is_tree( self) -> bool :
        
        g_prime = self.graph.copy()
        g_prime.add_edge( self.graph_sides[0], self.graph_sides[1])
        
        return nx.is_tree(g_prime)
    
    def explain_why_not_tree( self) -> str :
        
        g_prime = self.graph.copy()
        g_prime.add_edge( self.graph_sides[0], self.graph_sides[1])
        
        if nx.is_tree(g_prime) :
            return 'Graph is already a tree.'
        
        if not nx.is_connected(g_prime) :
            
            components         = list(nx.connected_components(g_prime))
            sorted_components  = [ sorted(component) for component in components ]
            component_strings  = [ f"[ {', '.join(component)} ]" for component in sorted_components ]
            components_summary = ', '.join(component_strings)
            
            return f'Graph is disconnected; found components: {components_summary}.'
        
        cycle_basis = nx.cycle_basis(g_prime)
        if cycle_basis :
            
            cycle_paths = []
            for cycle in cycle_basis :
                if not cycle :
                    continue
                
                cycle_nodes = list(cycle)
                cycle_nodes.append(cycle_nodes[0])
                cycle_paths.append(' -> '.join(cycle_nodes))
            
            if cycle_paths :
                formatted_cycles = [ f"* {cycle}" for cycle in cycle_paths ]
                cycles_summary   = '\n'.join(formatted_cycles)
                return f'Graph contains cycles:\n{cycles_summary}.'
        
        return 'Graph is not a tree, but the specific issue could not be determined.'
    
    def get_neighbors( self, component : str) -> list[str] | None :
        
        g_prime = self.graph.copy()
        for bridge in self.graph_bridges :
            for edge in self.graph_bridges[bridge] :
                g_prime.add_edge( edge[0], edge[1])
        
        try :
            comp_neighbors = list(g_prime.neighbors(component))
            comp_neighbors.sort()
            return comp_neighbors
        except nx.NetworkXError :
            print(f'❌ Error in get_neighbors: Component {component} not in the graph')
        
        return
    
    def get_path( self,
                  comp_A : str,
                  comp_B : str,
                  bridge : str | None = None) -> list[str] | None :
        
        g_prime = self.graph.copy()
        if bridge :
            if bridge in self.graph_bridges :
                for edge in self.graph_bridges[bridge] :
                    g_prime.add_edge( edge[0], edge[1])
            else :
                print(f'❌ Error in get_path: Bridge {bridge} not found')
        
        try :
            path = nx.shortest_path( g_prime, comp_A, comp_B)
            return list(path)
        except nx.NetworkXNoPath :
            print(f'❌ Error in get_path: No path found between {comp_A} and {comp_B}')
        
        return
