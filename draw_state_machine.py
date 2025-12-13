#!/usr/bin/env python3

from transitions.extensions import GraphMachine

from state_machine import StateMachine


class GraphicalStateMachine(StateMachine) :
    
    def __init__(self) :
        
        super().__init__( machine_cls           = GraphMachine,
                          show_state_attributes = True )
        
        return
    
    def draw_graph( self, filename : str = "state_machine.png") -> None :
        """
        Draw the graph with:
        * label 'enter' replaced by 'actions'
        * states as rounded rectangles with black borders
        * states fill-colored according to state_colors dict
        * transition arrows in red
        * transition labels in blue
        """
        graph        = self.machine.get_graph()
        state_colors = { state.name : state.color for state in self.states }
        
        # Apply customizations to each node
        for node in graph.nodes() :
            
            # Replace 'enter:' with 'actions:' in node labels
            node_attrs = graph.get_node(node).attr
            if 'label' in node_attrs :
                label = node_attrs['label']
                if 'enter:' in label :
                    new_label = label.replace( 'enter:', 'actions:')
                    graph.get_node(node).attr['label'] = new_label
            
            # Apply state style, border color and fill color
            graph.get_node(node).attr['style']     = 'rounded,filled'
            graph.get_node(node).attr['color']     = 'black'
            graph.get_node(node).attr['fillcolor'] = state_colors[node]
        
        # Apply colors to transitions (edges)
        for edge in graph.edges() :
            graph.get_edge( edge[0], edge[1]).attr['color']     = 'red'
            graph.get_edge( edge[0], edge[1]).attr['fontcolor'] = 'blue'
        
        # Draw the graph
        graph.draw( filename, prog = 'dot')
        
        return


if __name__ == "__main__" :
    
    graphical_state_machine = GraphicalStateMachine()
    graphical_state_machine.draw_graph()
