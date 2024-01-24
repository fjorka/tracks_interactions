from tracks_interactions.graph.family_graph import update_lineage_display


class EventHandler:
    def __init__(self, viewer, plot_widget, session):
        self.viewer = viewer
        self.plot_widget = plot_widget
        self.session = session

    def lineage_update(self, event):
        """update the plot_widget"""
        update_lineage_display(self.viewer, self.plot_widget, self.session)
