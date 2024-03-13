from copy import deepcopy

import dask.array as da
import numpy as np
from skimage.transform import resize
from sqlalchemy import and_
from sqlalchemy.orm import aliased

from tracks_interactions.db.db_model import CellDB, TrackDB


def newTrack_number(session):
    """
    input:
        - session
    output:
        - number of the new track
        - in the future consider getting first unused if fast enough
    """

    query = (
        session.query(TrackDB.track_id)
        .order_by(TrackDB.track_id.desc())
        .first()
    )

    if query is None:
        return 0

    return query[0] + 1


def get_descendants(session, active_label):
    """
    Function to recursively get all descendants of a given label.
    input:
        session
        active_label - label for which we want to get descendants
    output:
        descendants - list of descendants as row objects (not modifyable)
    """

    cte = (
        session.query(TrackDB)
        .filter(TrackDB.track_id == active_label)
        .cte(recursive=True)
    )

    cte_alias = aliased(cte, name="cte_alias")

    cte = cte.union_all(
        session.query(TrackDB).filter(
            TrackDB.parent_track_id == cte_alias.c.track_id
        )
    )

    # Join the CTE with TrackDB to get full TrackDB objects
    descendants = (
        session.query(TrackDB)
        .join(cte, TrackDB.track_id == cte.c.track_id)
        .all()
    )

    return descendants


def delete_trackDB(session, active_label):
    """
    Function to delete a track from trackDB.
    input:
        session
        active_label - label for which the track is cut
    """

    # get the acual track and check what will be done
    record = session.query(TrackDB).filter_by(track_id=active_label).first()

    # if the track is found
    if record is not None:
        # delete the track
        session.delete(record)

        # process descendants
        descendants = get_descendants(session, active_label)
        for track in descendants:
            if track.parent_track_id == active_label:
                cut_trackDB(session, track.track_id, track.t_begin)

        session.commit()

        status = f"Track {active_label} has been deleted."

    else:
        status = "Track not found"

    return status


def cut_trackDB(session, active_label, current_frame):
    """
    Function to cut a track in trackDB.
    input:
        session
        active_label - label for which the track is cut
        current_frame - current time point
    output:
        mitosis - True if the track is cut from mitosis
        new_track - number of the new track if the track is cut in the middle
    """

    # get the acual track and check what will be done
    record = session.query(TrackDB).filter_by(track_id=active_label).first()

    # if cut is called beyond the scope of a track
    # by accident cut on the first object of a track and it's a starting track
    if (
        (record.t_end < current_frame)
        or (record.t_begin > current_frame)
        or (
            (record.parent_track_id == -1)
            and (record.t_begin == current_frame)
        )
    ):
        new_track = None
        mitosis = False

    # cutting from mitosis
    elif (record.parent_track_id > -1) and (record.t_begin == current_frame):
        record.parent_track_id = -1

        # process descendants
        descendants = get_descendants(session, active_label)

        for track in descendants:
            track.root = active_label

        # indicate no new track
        new_track = None
        mitosis = True

        session.commit()

    # there is a true cut
    elif record.t_begin < current_frame:
        # modify the end of the track
        org_t_end = record.t_end
        record.t_end = current_frame - 1

        # add completely new track
        new_track = newTrack_number(session)

        track = TrackDB(
            track_id=new_track,
            parent_track_id=-1,
            root=new_track,
            t_begin=current_frame,
            t_end=org_t_end,
        )

        session.add(track)

        # process descendants
        descendants = get_descendants(session, active_label)

        for track in descendants[1:]:
            # change the value of the root track
            track.root = new_track

            # change for children
            if track.parent_track_id == active_label:
                track.parent_track_id = new_track

        mitosis = False
        session.commit()

    else:
        raise ValueError("Track situation unaccounted for")

    return mitosis, new_track


def _merge_t2(session, t2, t1, current_frame):
    """
    Function to cut a track in trackDB.
    This function is not touching merge_to
    input:
        session
        active_label - label for which the track is cut
        current_frame - current time point
    """

    # if there is remaining part at the beginning
    if t2.t_begin < current_frame:
        t2.t_end = current_frame - 1

    # the t2 track in merge stops existing
    else:
        session.delete(t2)

    # process descendants
    descendants = get_descendants(session, t2.track_id)

    for track in descendants[1:]:
        # change the value of the root track
        track.root = t1.root

        # change for children
        if track.parent_track_id == t2.track_id:
            track.parent_track_id = t1.track_id

    session.commit()


def _connect_t2(session, t2, t1, current_frame):
    """
    Function to connect t2 as an offspring of t1.
    This function is not touching merge_to
    input:
        session
        t2 - offsprint track
        t1 - parent track
        current_frame - frame were t2 will be starting from mitosis
    """

    # if there is a remaining part at the beginning
    if t2.t_begin < current_frame:
        # create a new track
        new_track = newTrack_number(session)

        # check if the t2_before needs to become its own root
        new_root = new_track if t2.root == t2.track_id else deepcopy(t2.root)

        track = TrackDB(
            track_id=new_track,
            parent_track_id=deepcopy(t2.parent_track_id),
            root=new_root,
            t_begin=deepcopy(t2.t_begin),
            t_end=current_frame - 1,
        )

        session.add(track)

        # modify t2
        t2.t_begin = current_frame

    else:
        new_track = None

    # modify family relations
    t2.parent_track_id = t1.track_id

    # process descendants
    descendants = get_descendants(session, t2.track_id)

    for tr in descendants:
        # change the value of the root track
        tr.root = t1.root

    session.commit()

    # return the new track number (1st part of t2)
    return new_track


def integrate_trackDB(session, operation, t1_ind, t2_ind, current_frame):
    """
    Function to merge or connect two tracks in trackDB.
    For the opperation to happen t1 has to exist on current_frame - 1 time point
    input:
        session
        operation - "merge" or "connect"
        t1_ind - label of the first track
        t2_ind - label of the second track
        current_frame - current time point
    output:
        t1_after - label of the new track if t1 is cut
        t2_before - label of the new track if t2 is cut
    """

    # get tracks of interest
    t1 = session.query(TrackDB).filter_by(track_id=t1_ind).first()
    t2 = session.query(TrackDB).filter_by(track_id=t2_ind).first()

    # if t1 doesn't start yet
    if t1.t_begin >= current_frame:
        return -1

    # if t1 is to be cut
    if (t1.t_begin < current_frame) and (t1.t_end >= current_frame):
        _, t1_after = cut_trackDB(session, t1.track_id, current_frame)

    # if t1 is ending before current_frame
    elif t1.t_end < current_frame:
        t1_after = None

        # if there is offsprint detach them as separate trees
        descendants = get_descendants(session, t1.track_id)

        for track in descendants[1:]:
            # cut off the children if they start at a different time
            if (track.parent_track_id == t1.track_id) and (
                track.t_begin != current_frame
            ):
                # this route will call descendants twice but I expect it to be rare
                _, _ = cut_trackDB(session, track.track_id, track.t_begin)

    if operation == "merge":
        # change t1_before
        # does it account for merging with gaps only?
        t1.t_end = t2.t_end

        # merge t2 to t1
        _merge_t2(session, t2, t1, current_frame)
        t2_before = None

    elif operation == "connect":
        # change t1
        t1.t_end = current_frame - 1
        t2_before = _connect_t2(session, t2, t1, current_frame)

    else:
        raise ValueError(
            f"Unknown operation '{operation}'. Use 'merge' or 'connect'."
        )

    return t1_after, t2_before


def _get_track_bbox(query):
    """
    Helper function that returns bounding box of a track.
    It's called by cut_cellsDB function when this database is modified.

    input:
        query - list of row objects
    output:
        row_start, row_stop, column_start, column_stop- bounding box
        t_stop - last time point of the track
    """

    # find bounding boxes of the track
    row_start = min(cell.bbox_0 for cell in query)
    row_stop = max(cell.bbox_2 for cell in query)
    column_start = min(cell.bbox_1 for cell in query)
    column_stop = max(cell.bbox_3 for cell in query)
    t_start = min(cell.t for cell in query)
    t_stop = max(cell.t for cell in query)

    return (t_start, t_stop, row_start, row_stop, column_start, column_stop)


def modify_track_cellsDB(
    session, active_label, current_frame, new_track, direction="after"
):
    """

    input:
        session
        active_label - label for which the track is cut
        current_frame - current time point
    output:
        track_bbox - bounding box of the track
    """

    # query CellDB
    # order by time
    if direction == "after":
        query = (
            session.query(CellDB)
            .filter(
                and_(
                    CellDB.track_id == active_label, CellDB.t >= current_frame
                )
            )
            .order_by(CellDB.t)
            .all()
        )
    elif direction == "before":
        query = (
            session.query(CellDB)
            .filter(
                and_(CellDB.track_id == active_label, CellDB.t < current_frame)
            )
            .order_by(CellDB.t)
            .all()
        )
    elif direction == "all":
        query = (
            session.query(CellDB).filter(CellDB.track_id == active_label).all()
        )
    else:
        raise ValueError("Direction should be 'all', 'before' or 'after'.")

    assert len(query) > 0, "No cells found for the given track"

    # get the track_bbox
    track_bbox = _get_track_bbox(query)

    # change track_ids
    if new_track is not None:
        for cell in query:
            cell.track_id = new_track
    # or delete the cells
    else:
        for cell in query:
            session.delete(cell)

    session.commit()

    return track_bbox


def add_CellDB_to_DB(viewer):
    """
    Function to add a cell to the database.
    """

    current_label = viewer.layers["Labels"].selected_label
    frame = viewer.dims.current_step[0]

    corner_pixels = viewer.layers["Labels"].corner_pixels

    sc_r_start = corner_pixels[0, 1]
    sc_r_stop = corner_pixels[1, 1]
    sc_c_start = corner_pixels[0, 2]
    sc_c_stop = corner_pixels[1, 2]

    visible_labels = viewer.layers["Labels"].data[
        frame, sc_r_start:sc_r_stop, sc_c_start:sc_c_stop
    ]

    # start the object
    cell = CellDB(id=current_label, t=frame, track_id=current_label)

    # get properties
    coords = np.argwhere(visible_labels == current_label)
    rmin, cmin = coords.min(axis=0)
    rmax, cmax = coords.max(axis=0)

    coords_mean = coords.mean(axis=0)
    cell.row = int(coords_mean[0] + sc_r_start)
    cell.col = int(coords_mean[1] + sc_c_start)

    cell.bbox_0 = int(rmin + sc_r_start)
    cell.bbox_1 = int(cmin + sc_c_start)
    cell.bbox_2 = int(rmax + sc_r_start + 1)
    cell.bbox_3 = int(cmax + sc_c_start + 1)

    roi = visible_labels[rmin : rmax + 1, cmin : cmax + 1]
    cell.mask = roi == current_label

    return cell


def calculate_cell_signals(cell, ch_list=None, ch_names=None, ring_width=5):
    """
    Function to calculate signals of a single cell.
    If a single plane given, frame information of a cell is not used.
    """

    # caclulate cell area
    mask = np.array(cell.mask)
    area = mask.sum()

    cell_dict = {"area": int(area)}

    if ch_list is None:
        return cell_dict

    # create a ring mask
    cyto_mask = resize(
        mask,
        np.array(mask.shape) + 2 * ring_width,
        order=0,
        anti_aliasing=False,
    )
    cell_in_cyto_mask = np.zeros_like(cyto_mask)
    cell_in_cyto_mask[
        ring_width:-ring_width, ring_width:-ring_width
    ] = cell.mask
    cyto_mask[cell_in_cyto_mask] = 0

    # check how to cut boxes

    # calculate positions
    r_start = cell.bbox_0 - ring_width
    c_start = cell.bbox_1 - ring_width
    r_paste_start = c_paste_start = 0

    # account for edge cases
    if r_start < 0:
        r_paste_start = -r_start
        r_start = 0
    if c_start < 0:
        c_paste_start = -c_start
        c_start = 0

    ch = ch_list[0]
    if ch.ndim == 3:
        r_end = np.min([ch.shape[1], cell.bbox_2 + ring_width])
        c_end = np.min([ch.shape[2], cell.bbox_3 + ring_width])
    else:
        r_end = np.min([ch.shape[0], cell.bbox_2 + ring_width])
        c_end = np.min([ch.shape[1], cell.bbox_3 + ring_width])

    # get signals for all the channels
    if ch_names is None:
        ch_names = [f"ch{i}" for i in range(len(ch_list))]

    for ch, ch_name in zip(ch_list, ch_names):
        # create a box for the channel
        ch_box = np.zeros_like(cyto_mask).astype(ch.dtype)

        # get channel ring boxes
        if ch.ndim == 3:
            signal = ch[cell.t, r_start:r_end, c_start:c_end]
        else:
            signal = ch[r_start:r_end, c_start:c_end]

        # paste the signal into the box
        ch_box[
            r_paste_start : (r_paste_start + signal.shape[0]),
            c_paste_start : (c_paste_start + signal.shape[1]),
        ] = signal

        # calculate signals
        ch_nuc = np.mean(ch_box[cell_in_cyto_mask])
        ch_cyto = np.mean(ch_box[cyto_mask])

        # compute if necessary
        if type(ch_nuc) == da.core.Array:
            ch_nuc = ch_nuc.compute()
            ch_cyto = ch_cyto.compute()

        # add to the dictionary
        cell_dict[ch_name + "_nuc"] = ch_nuc
        cell_dict[ch_name + "_cyto"] = ch_cyto

    return cell_dict
