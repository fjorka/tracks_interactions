import numpy as np
import pandas as pd
import networkx as nx
from pyqtgraph import (
    GraphicsLayoutWidget,
    TextItem,
    mkColor,
    mkPen,
)
from qtpy.QtCore import Qt

from tracks_interactions.db.db_model import TrackDB


class FamilyGraphWidget(GraphicsLayoutWidget):
    def __init__(self, viewer, session):
        super().__init__()

        self.setContextMenuPolicy(Qt.NoContextMenu)

        self.session = session
        self.viewer = viewer
        self.labels = self.viewer.layers['Labels']

        # initialize graph
        self.plot_view = self.addPlot(
            title='Lineage tree', labels={'bottom': 'Time'}
        )
        self.plot_view.hideAxis('left')
        self.t_max = self.viewer.dims.range[0][1]
        self.plot_view.setXRange(0, self.t_max)
        self.plot_view.setMouseEnabled(x=True, y=True)
        self.plot_view.setMenuEnabled(False)

        # Connect the plotItem's mouse click event
        self.plot_view.scene().sigMouseClicked.connect(self.onMouseClick)

        # initialize time line
        pen = mkPen(color=(255, 255, 255), xwidth=1)
        init_position = self.viewer.dims.current_step[0]
        self.time_line = self.plot_view.addLine(x=init_position, pen=pen)

        # connect time slider event
        self.viewer.dims.events.current_step.connect(self.update_family_line)

        # connect label selection event
        self.labels.events.selected_label.connect(self.update_lineage_display)

    def onMouseClick(self, event):
        """
        Mouse click event handler.
        Left - selection of a track
        Right - selection of a time point
        """
        vb = self.plot_view.vb
        scene_coords = event.scenePos()

        if self.plot_view.sceneBoundingRect().contains(scene_coords):
            mouse_point = vb.mapSceneToView(scene_coords)
            x_val = mouse_point.x()
            y_val = mouse_point.y()

            ############################################################
            # find which track was selected
            dist = float('inf')
            selected_n = None

            if self.tree is not None:
                for n in self.tree.traverse():
                    if n.is_root():
                        pass
                    else:
                        # self.viewer.status=f'Clicked on {n.name}, {y_val} of {n.y}, {x_val} from {n.start} to {n.stop}!'
                        if (n.start <= x_val) and (n.stop >= x_val):
                            dist_track = abs(n.y - y_val)
                            if dist_track < dist:
                                dist = dist_track
                                selected_n = n
            ############################################################

            if event.button() == Qt.LeftButton:
                # move in time
                self.viewer.dims.set_point(0, round(x_val))

                # capture if it tries to get attribute from None
                try:
                    self.viewer.status = f'Selected track: {selected_n.name}'
                    self.labels.selected_label = selected_n.name

                except AttributeError:
                    print(
                        f'Click at {scene_coords.x()},{scene_coords.x()} translated to {x_val}, {y_val}'
                    )

            # right click - change of status
            elif event.button() == Qt.RightButton:
                if selected_n is not None:
                    # flip the status
                    track = (
                        self.session.query(TrackDB)
                        .filter(TrackDB.track_id == selected_n.name)
                        .first()
                    )
                    track.accepted_tag = not track.accepted_tag
                    self.session.commit()

                    # update the tree
                    self.update_lineage_display()

                    # update viewer status
                    self.viewer.status = f'Track {selected_n.name} accepted status: {track.accepted_tag}.'

        else:
            self.viewer.status = 'No tree to select from.'

    def update_family_line(self):
        """
        Update of the family line when slider position is moved.
        """
        # line_position = event.value # that emitts warning for reasons that I don't understand
        line_position = self.viewer.dims.current_step[0]
        self.time_line.setValue(line_position)

    def update_lineage_display(self):
        """
        Update of the lineage display when a new label is selected.
        """

        # Clear all elements except the time line
        items_to_remove = self.plot_view.items[
            1:
        ]  # Get all items except the time line
        for item in items_to_remove:
            self.plot_view.removeItem(item)

        # get an active label
        if self.viewer.layers['Labels'].selected_label > 0:
            self.active_label = int(self.labels.selected_label)
        else:
            self.active_label = int(self.labels.metadata['persistent_label'])

        # check if the label is in the database
        query = (
            self.session.query(TrackDB)
            .filter(TrackDB.track_id == self.active_label)
            .first()
        )

        # actions based on finding the label in the database
        if query is not None:
            # get the root value
            root = query.root

            # update viewer status
            self.viewer.status = f'Family of track number {root}.'

            # buid the tree
            self.tree = build_Newick_tree(self.session, root)

            # update the widget with the tree
            self.render_tree_view(self.tree)

        else:
            self.viewer.status = 'Error - no such label in the database.'

    def render_tree_view(self, G):
        """
        Render the hierarchical tree using NetworkX and PyQtGraph, 
        assuming node positions are stored in the 'pos' attribute of each node.
        
        G: NetworkX graph with node positions stored in 'pos' attributes.
        """
        y_max = 1
        y_min = 0

        # Iterate over nodes in the graph
        for node in G.nodes():

            node_data = G.nodes[node]
            node_name = node_data['name']

            # Get position in time (x-coordinates: start and stop)
            x1 = node_data['start']
            x2 = node_data['stop']
            x_signal = [x1, x2]

            # Get y-coordinate from the node's 'pos' attribute
            y_signal = np.array([node_data['y']]).repeat(2)
            y_max = np.max([y_signal[0], y_max])
            y_min = np.min([y_signal[0], y_min])

            # Get color based on the label
            label_color = self.labels.get_color(node_name)

            # Pen color and style adjustments based on the node's state
            if node_name == self.active_label:
                pen_color = mkColor((label_color * 255).astype(int))
                pen = mkPen(color=pen_color, width=4)
            else:
                label_color[-1] = 0.4
                pen_color = mkColor((label_color * 255).astype(int))
                pen = mkPen(color=pen_color, width=2)

            if not node_data['accepted']:
                pen.setStyle(Qt.DotLine)

            # Plot the horizontal line for the node
            self.plot_view.plot(x_signal, y_signal, pen=pen)

            # Add text label for the node
            if node_data['accepted']:
                text_item = TextItem(str(node_name), anchor=(1, 1), color='green')
            else:
                text_item = TextItem(str(node_name), anchor=(1, 1))

            text_item.setPos(x2, node_data['y'])
            self.plot_view.addItem(text_item)

            # Plot vertical lines to children
            for child in G.successors(node):
                child_data = G.nodes[child]

                # Get vertical line (constant x and different y values)
                x_signal = [x2, x2]
                y_signal = [node_data['y'], child_data['y']]
                self.plot_view.plot(x_signal, y_signal, pen=pen)

        # Set plot axis limits
        self.plot_view.setXRange(0, self.t_max)
        self.plot_view.setYRange(y_min -0.1*abs(y_min), y_max + 0.1*abs(y_max))

def reingold_tilford(tree, node=None, depth=0, x_offset=0, x_spacing=1):
    """
    Recursive function to apply Reingold-Tilford algorithm for binary trees.
    
    Args:
        tree: NetworkX DiGraph representing the tree.
        node: Current node being processed (if None, starts at the root).
        depth: Current depth level in the tree.
        x_offset: Horizontal position offset for the current node.
        x_spacing: Spacing between nodes.
    
    Returns:
        pos: Dictionary of node positions with x, y coordinates.
    """
    # If no node is specified, start from the root node (node with in-degree 0)
    if node is None:
        node = next(n for n in tree.nodes() if tree.in_degree(n) == 0)

    if tree.out_degree(node) == 0:  # If leaf node
        return {node: (x_offset, -depth)}
    
    children = list(tree.successors(node))
    
    # Get positions of left and right subtrees
    pos_left = reingold_tilford(tree, children[0], depth+1, x_offset, x_spacing) if len(children) > 0 else {}
    pos_right = reingold_tilford(tree, children[1], depth+1, x_offset + len(pos_left) * x_spacing, x_spacing) if len(children) > 1 else {}
    
    # Calculate the center x position of the current node
    num_left = len(pos_left)
    num_right = len(pos_right)
    
    # Center node between left and right children
    x_center = x_offset + (num_left + num_right - 1) / 2.0 * x_spacing
    pos = {node: (x_center, -depth)}
    
    # Merge positions of subtrees
    pos.update(pos_left)
    pos.update(pos_right)
    
    return pos

def _add_children(G, parent, df, n=2):
    """
    Recursively adds children to the NetworkX graph from a dataframe.
    
    G - NetworkX graph
    parent - parent node ID
    df - dataframe with information about children
    n - counter for numbering nodes
    """
    children = df[df['parent_track_id'] == parent]

    for _, row in children.iterrows():
        child_id = row['track_id']
        G.add_node(child_id, name=row['track_id'], start=row['t_begin'], stop=row['t_end'], accepted=row['accepted_tag'], num=n)
        G.add_edge(parent, child_id)

        n += 1
        n = _add_children(G, child_id, df, n)

    return n

def build_Newick_tree(session, root_id):
    """
    Build a NetworkX graph to represent the hierarchical tree structure.
    
    session - database session
    root_id - ID of the root node
    """
    # Get info about the family from the database
    query = session.query(TrackDB).filter(TrackDB.root == root_id)
    df = pd.read_sql(query.statement, session.bind)

    # Ensure the root exists
    assert len(df) > 0, 'No data for this root_id'

    # Create a NetworkX graph
    G = nx.DiGraph()

    # Add the root (trunk) node
    trunk_row = df[df['track_id'] == root_id]
    G.add_node(root_id, name=root_id, start=trunk_row['t_begin'].values[0], stop=trunk_row['t_end'].values[0], accepted=bool(trunk_row['accepted_tag'].values[0]), num=1)

    # Recursively add children
    _add_children(G, root_id, df)

    # add rendering
    pos = reingold_tilford(G)
    y_values = {node: x for node, (x, y) in pos.items()}
    nx.set_node_attributes(G, y_values, 'y')

    # Return the NetworkX graph
    return G
