import tracks_interactions.db.db_functions as fdb
from napari import Viewer


def modify_labels(viewer: Viewer, track_bbox, active_label, new_track):
    """
    Function to change values of the labels layer.
    """

    # modify labels
    labels = viewer.layers["Labels"].data

    sel = labels[
        track_bbox[0] : track_bbox[1],
        track_bbox[2] : track_bbox[3],
        track_bbox[4] : track_bbox[5],
    ]
    sel[sel == active_label] = new_track
    labels[
        track_bbox[0] : track_bbox[1],
        track_bbox[2] : track_bbox[3],
        track_bbox[4] : track_bbox[5],
    ] = sel

    viewer.layers["Labels"].data = labels


####################################################################################################
####################################################################################################
####################################################################################################


def cut_track_function(viewer: Viewer, session):
    ################################################################################################
    # orient yourself - figure what is asked for

    # get the position in time
    current_frame = viewer.dims.current_step[0]

    # get my label
    active_label = int(viewer.layers["Labels"].selected_label)

    ################################################################################################
    # perform database operations

    # cut trackDB
    mitosis, new_track = fdb.cut_trackDB(session, active_label, current_frame)

    # if cutting from mitosis
    if mitosis:
        fdb.cut_cellsDB_mitosis(session, active_label)

        # trigger family tree update
        viewer.layers["Labels"].selected_label = active_label

    # if cutting in the middle of a track
    elif new_track:
        track_bbox = fdb.cut_cellsDB(
            session, active_label, current_frame, new_track
        )

        # modify labels
        modify_labels(viewer, track_bbox, active_label, new_track)

        # trigger family tree update
        viewer.layers["Labels"].selected_label = new_track

    # if clicked by mistake
    else:
        pass

    ################################################################################################
    # change viewer status
    viewer.status = f"Track {active_label} has been cut."


####################################################################################################
####################################################################################################
####################################################################################################


def merge_track_function(viewer: Viewer, t1: int, session):
    """
    This function is called by the even handler
    when the user wants to perform a merging operation.
    t1 is an index of the track receiving the merge.
    """
    ################################################################################################
    # orient yourself - figure what is asked for

    # get the position in time
    current_frame = viewer.dims.current_step[0]

    # get my label
    t2 = int(viewer.layers["Labels"].selected_label)

    ################################################################################################
    # check if the request is possible
    if t1 == t2:
        viewer.status = "Error - cannot merge a track with itself."
        return

    ################################################################################################
    # perform database operations

    # cut trackDB
    t1_after = fdb.merge_trackDB(session, t1, t2, current_frame)

    if t1_after == -1:
        viewer.status = (
            "Error - cannot merge to a track that hasn't started yet."
        )
        return

    if t1_after is not None:
        # modify cellsDB of t1
        track_bbox_t1 = fdb.cut_cellsDB(session, t1, current_frame, t1_after)

        # modify labels of t1
        modify_labels(viewer, track_bbox_t1, t1, t1_after)

    # modify cellsDB of t2
    track_bbox_t2 = fdb.cut_cellsDB(session, t2, current_frame, t1)

    # modify labels of t2
    modify_labels(viewer, track_bbox_t2, t2, t1)

    # trigger family tree update
    viewer.layers["Labels"].selected_label = t1

    ################################################################################################
    # change viewer status
    viewer.status = f"Track {t2} has been merged to {t1}. Track {t1_after} has been created."


####################################################################################################
####################################################################################################
####################################################################################################
