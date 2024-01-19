import tracks_interactions.db.db_functions as fdb
from napari import Viewer


def cut_track_function(viewer: Viewer, session):
    ####################################################################################################
    # orient yourself - figure what is asked for

    # get the position in time
    current_frame = viewer.dims.current_step[0]

    # get my label
    active_label = int(viewer.layers["Labels"].selected_label)

    # find new track number
    new_track = fdb.newTrack_number(session)

    ####################################################################################################
    # perform database operations

    # get descendants
    descendants = fdb.get_descendants(session, active_label)

    # Database operations
    # cut cellsDB
    track_bbox = fdb.cut_cellsDB(
        session, descendants, active_label, current_frame, new_track
    )

    # cut trackDB
    fdb.modify_trackDB(
        session, descendants, active_label, current_frame, new_track
    )

    ####################################################################################################
    # modify labels
    labels = viewer.layers["Labels"].data

    if track_bbox is not None:
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

    ####################################################################################################
    # update lineage graph
    viewer.layers["Labels"].selected_label = new_track

    ####################################################################################################
    # change viewer status
    viewer.status = f"Track {active_label} has been cut."
