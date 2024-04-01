import tensorstore as ts

from napari import Viewer


def modify_labels(viewer: Viewer, track_bbox, active_label, new_track):
    """
    Function to change values of the labels layer.
    track_bbox is a tuple of 6 integers.
    """

    # modify labels
    labels = viewer.layers['Labels'].data
    labels_type = type(labels)

    sel = labels[
        track_bbox[0] : track_bbox[1] + 1,
        track_bbox[2] : track_bbox[3],
        track_bbox[4] : track_bbox[5],
    ]

    if labels_type == ts.TensorStore:
        sel = sel.read().result()

    sel[sel == active_label] = new_track
    labels[
        track_bbox[0] : track_bbox[1] + 1,
        track_bbox[2] : track_bbox[3],
        track_bbox[4] : track_bbox[5],
    ] = sel

    if labels_type == ts.TensorStore:
        viewer.layers['Labels'].refresh()
    else:
        viewer.layers['Labels'].data = labels
