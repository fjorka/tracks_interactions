from copy import deepcopy

import dask.array as da
import numpy as np
from skimage.transform import resize
from sqlalchemy import and_
from sqlalchemy.orm import aliased
from sqlalchemy.orm.attributes import flag_modified

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

    cte_alias = aliased(cte, name='cte_alias')

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
        # process descendants
        descendants = get_descendants(session, active_label)
        for track in [x for x in descendants if x.track_id != active_label]:
            if track.parent_track_id == active_label:
                cut_trackDB(session, track.track_id, track.t_begin)

        # delete the track
        session.delete(record)

        session.commit()

        status = f'Track {active_label} has been deleted.'

    else:
        status = 'Track not found'

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

        # account for a situation when it's a gap around the cut
        cells_t = (
            session.query(CellDB.t).filter_by(track_id=active_label).all()
        )
        t_start = min(
            [cell[0] for cell in cells_t if cell[0] >= current_frame]
        )
        t_stop = max([cell[0] for cell in cells_t if cell[0] < current_frame])
        record.t_end = t_stop

        # add completely new track
        new_track = newTrack_number(session)

        track = TrackDB(
            track_id=new_track,
            parent_track_id=-1,
            root=new_track,
            t_begin=t_start,
            t_end=org_t_end,
        )

        session.add(track)

        # process descendants
        descendants = get_descendants(session, active_label)

        for track in [x for x in descendants if x.track_id != active_label]:
            # change the value of the root track
            track.root = new_track

            # change for children
            if track.parent_track_id == active_label:
                track.parent_track_id = new_track

        mitosis = False
        session.commit()

    else:
        raise ValueError('Track situation unaccounted for')

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

    # process descendants
    descendants = get_descendants(session, t2.track_id)

    # if there is remaining part at the beginning
    if t2.t_begin < current_frame:
        t2.t_end = current_frame - 1

    # the t2 track in merge stops existing
    else:
        session.delete(t2)

    # for everyone except the t2 track
    for track in [x for x in descendants if x.track_id != t2.track_id]:
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

        # if there is t1 offsprint detach them as separate trees
        descendants = get_descendants(session, t1.track_id)

        for track in [x for x in descendants if x.track_id != t1.track_id]:
            # cut off the children if they start at a different time
            if (track.parent_track_id == t1.track_id) and (
                track.t_begin != current_frame
            ):
                # this route will call descendants twice but I expect it to be rare
                _, _ = cut_trackDB(session, track.track_id, track.t_begin)

    if operation == 'merge':
        # change t1_before
        # does it account for merging with gaps only?
        t1.t_end = t2.t_end

        # merge t2 to t1
        _merge_t2(session, t2, t1, current_frame)
        t2_before = None

    elif operation == 'connect':
        # change t1
        t1.t_end = current_frame - 1
        t2_before = _connect_t2(session, t2, t1, current_frame)

    else:
        raise ValueError(
            f"Unknown operation '{operation}'. Use 'merge' or 'connect'."
        )

    return t1_after, t2_before


def cellsDB_after_trackDB(
    session, active_label, current_frame, new_track, direction='after'
):
    """

    input:
        session
        active_label - label for which the track is cut
        current_frame - current time point
    """

    # query CellDB
    # order by time
    if direction == 'after':
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
    elif direction == 'before':
        query = (
            session.query(CellDB)
            .filter(
                and_(CellDB.track_id == active_label, CellDB.t < current_frame)
            )
            .order_by(CellDB.t)
            .all()
        )
    elif direction == 'all':
        query = (
            session.query(CellDB).filter(CellDB.track_id == active_label).all()
        )
    else:
        raise ValueError("Direction should be 'all', 'before' or 'after'.")

    assert len(query) > 0, 'No cells found for the given track'

    # change track_ids
    if new_track is not None:
        for cell in query:
            cell.track_id = new_track
    # or delete the cells
    else:
        for cell in query:
            session.delete(cell)

    session.commit()


def trackDB_after_cellDB(session, cell_id, current_frame):
    """
    Function to deal with tracks upon cell removal/adding
    cell_id - id of the removed cell
    current_frame
    """

    track = session.query(TrackDB).filter(TrackDB.track_id == cell_id).first()

    # create a new track object if necessary
    if track is None:

        track = TrackDB(
            track_id=cell_id,
            t_begin=current_frame,
            t_end=current_frame,
            parent_track_id=-1,
            root=cell_id,
        )
        session.add(track)
        session.commit()

    # query for cells
    cells_t = session.query(CellDB.t).filter(CellDB.track_id == cell_id).all()

    # there are cells - adjust the track
    if len(cells_t) > 0:

        cells_t = [cell[0] for cell in cells_t]

        t_min = min(cells_t)
        t_max = max(cells_t)

        if track.t_begin != t_min:
            # cell added to the left
            # cut off this track
            _, new_track = cut_trackDB(session, cell_id, track.t_begin)
            track.t_begin = t_min

        if track.t_end != t_max:
            # cell added to the right
            # cut off the offspring
            offspring = (
                session.query(TrackDB)
                .filter(TrackDB.parent_track_id == cell_id)
                .all()
            )

            for child in offspring:
                _, new_track = cut_trackDB(
                    session, child.track_id, child.t_begin
                )

            track.t_end = t_max

    # remove the track
    else:
        session.delete(track)

    session.commit()


def remove_CellDB(session, cell_id, current_frame):
    """
    Function to remove a cell from the database.
    """

    cell = (
        session.query(CellDB)
        .filter(CellDB.track_id == cell_id)
        .filter(CellDB.t == current_frame)
        .first()
    )

    if cell is not None:

        session.delete(cell)
        session.commit()

        # deal with the tracks
        trackDB_after_cellDB(session, cell_id, current_frame)

    else:
        print('Cell not found')


def add_new_core_CellDB(session, current_frame, cell):
    """
    session
    current_frame
    cell - regionprops format cell
    """

    # start the object
    cell_db = CellDB(id=cell.label, t=current_frame, track_id=cell.label)

    cell_db.row = int(cell.centroid[0])
    cell_db.col = int(cell.centroid[1])

    cell_db.bbox_0 = int(cell.bbox[0])
    cell_db.bbox_1 = int(cell.bbox[1])
    cell_db.bbox_2 = int(cell.bbox[2])
    cell_db.bbox_3 = int(cell.bbox[3])

    cell_db.mask = cell.image

    session.add(cell_db)
    session.commit()

    return cell_db


def add_new_CellDB(
    session,
    current_frame,
    cell,
    modified=True,
    ch_list=None,
    ch_names=None,
    ring_width=5,
):
    """
    Function to add a complete cell
    """

    cell_db = add_new_core_CellDB(session, current_frame, cell)

    # add signals to the cell
    new_signals = calculate_cell_signals(
        cell_db, ch_list=ch_list, ch_names=ch_names, ring_width=ring_width
    )
    cell_db.signals = new_signals

    # add modified tag to the cell
    tags = {}
    if modified:
        tags['modified'] = True
        cell_db.tags = tags

    session.commit()

    # deal with the tracks
    trackDB_after_cellDB(session, cell_db.track_id, current_frame)


def calculate_cell_signals(cell, ch_list=None, ch_names=None, ring_width=5):
    """
    Function to calculate signals of a single cell.
    If a single plane given, frame information of a cell is not used.
    """

    # caclulate cell area
    mask = np.array(cell.mask)
    area = mask.sum()

    cell_dict = {'area': int(area)}

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
    cell_in_cyto_mask[ring_width:-ring_width, ring_width:-ring_width] = (
        cell.mask
    )
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
        ch_names = [f'ch{i}' for i in range(len(ch_list))]

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
        cell_dict[ch_name + '_nuc'] = ch_nuc
        cell_dict[ch_name + '_cyto'] = ch_cyto

    return cell_dict


def get_track_note(session, active_label):
    """
    Function to retrieve the free format note for a given track.
    """

    query = session.query(TrackDB).filter_by(track_id=active_label).first()

    if query is None:
        return None
    else:
       return query.notes 


def save_track_note(session,active_label,note):
    """
    Save a given note to the track in the database.
    """

    track = session.query(TrackDB).filter_by(track_id=active_label).first()

    if track is None:
        sts = f'Error - track {active_label} is not present in the database.'

    else:
        track.notes = note
        flag_modified(track, 'notes')
        session.commit()

        sts = f'Note for track {active_label} saved in the database.'

    return sts


def tag_cell(session,active_cell,frame,annotation):
    """
    Function to give a tag to a cell in the CellDB table.
    """

    cell_list = (
        session.query(CellDB)
        .filter(CellDB.t == frame)
        .filter(CellDB.track_id == active_cell)
        .all()
    )

    if len(cell_list) == 0:
        sts = 'Error - no cell found at this frame.'
    elif len(cell_list) > 1:
        sts = f'Error - Multiple cells found for {active_cell} at {frame}.'
    else:
        cell = cell_list[0]
        tags = cell.tags

        current_state = tags.get(annotation, False)

        tags[annotation] = not current_state

        cell.tags = tags
        flag_modified(cell, 'tags')
        session.commit()

        # set status and update graph
        sts = f'Tag {annotation} was set to {not current_state}.'

    return sts
