from tracks_interactions.graph.family_graph import (
    update_family_line,
    update_lineage_display,
)


class EventHandler:
    def __init__(self, viewer, plot_widget, session):
        self.viewer = viewer
        self.plot_widget = plot_widget
        self.session = session

    def lineage_update(self, event):
        """update the plot_widget"""
        update_lineage_display(self.viewer, self.plot_widget, self.session)

    def time_line_update(self, event):
        """update the time line"""
        slider_position = event.value
        update_family_line(self.plot_widget, slider_position)
