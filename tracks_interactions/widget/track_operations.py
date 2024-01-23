import tracks_interactions.db.db_functions as fdb
from napari import Viewer


def cut_track_function(viewer: Viewer, session):
    ####################################################################################################
    # orient yourself - figure what is asked for

    # get the position in time
    current_frame = viewer.dims.current_step[0]

    # get my label
    active_label = int(viewer.layers["Labels"].selected_label)

    ####################################################################################################
    # perform database operations

    # cut trackDB
    mitosis, new_track = fdb.cut_trackDB(session, active_label, current_frame)

    # if cutting from mitosis
    if mitosis:
        fdb.cut_cellsDB_mitosis(session, active_label)

        viewer.layers["Labels"].selected_label = active_label

    # if cutting in the middle of a track
    elif new_track:
        track_bbox = fdb.cut_cellsDB(
            session, active_label, current_frame, new_track
        )

        # modify labels
        labels = viewer.layers["Labels"].data

        sel = labels[
            current_frame : track_bbox[0],
            track_bbox[1] : track_bbox[2],
            track_bbox[3] : track_bbox[4],
        ]
        sel[sel == active_label] = new_track
        labels[
            current_frame : track_bbox[0],
            track_bbox[1] : track_bbox[2],
            track_bbox[3] : track_bbox[4],
        ] = sel

        viewer.layers["Labels"].data = labels

        viewer.layers["Labels"].selected_label = new_track

    # if clicked by mistake
    else:
        pass

    ####################################################################################################
    # change viewer status
    viewer.status = f"Track {active_label} has been cut."
