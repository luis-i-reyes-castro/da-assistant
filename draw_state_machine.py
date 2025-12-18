#!/usr/bin/env python3

import re
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
        graph = self.machine.get_graph()
        
        # Apply customizations to each node
        for node in graph.nodes() :
            
            # Replace node labels
            if 'label' in node.attr :
                label = node.attr['label']
                label = re.sub( r"^(\w+)", r"STATE '\1'", label)
                label = label.replace( '+', '·')
                label = label.replace( '- enter:', '[>] do:')
                label = label.replace( '- exit:', '[>] on exit:')
                node.attr['label'] = label
            
            # Apply state style and border color
            node.attr['style'] = 'rounded,filled'
            node.attr['color'] = 'black'
            
            # Apply orange fill color to agent nodes
            node_color = "orange" if ( "agent" in node.name ) else "white"
            node.attr['fillcolor'] = node_color
        
        # Apply colors to transitions (edges)
        for edge in graph.edges() :
            edge.attr['color']     = 'red'
            edge.attr['fontcolor'] = 'blue'
        
        # Draw the graph
        graph.draw( filename, prog = 'dot')
        
        return


if __name__ == "__main__" :
    
    graphical_state_machine = GraphicalStateMachine()
    graphical_state_machine.draw_graph()
