from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from numba import njit
from sqlalchemy import and_
from sqlalchemy.orm import aliased
from ultrack.tracks.graph import _fast_path_transverse, create_tracks_forest

from tracks_interactions.db.db_model import NO_PARENT, CellDB, TrackDB


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

    # by accident cut on the first object of a track
    if (record.parent_track_id == -1) and (record.t_begin == current_frame):
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


# def merge_trackDB(session, merger_from, merger_to, current_frame):
#     """
#     Function to merge two tracks in trackDB.
#     """

#     # change the end of the merger to
#     record = session.query(TrackDB).filter_by(track_id=merger_to).first()
#     record.t_end = session.query(TrackDB).filter_by(track_id=merger_from).first().t_end


#     # check if merger_from is cut or is it a beginning
#     m_from_begin = session.query(TrackDB).filter_by(track_id=merger_from).first().t_begin

#     # entire m_from is being merget to m_to
#     if m_from_begin >= current_frame:

#     else:


#         # change the root of the merger_to
#         session.query(TrackDB).filter_by(track_id=merger_from).first().root = merger_to

#         # change the parent_id of the merger_from
#         session.query(TrackDB).filter_by(track_id=merger_from).first().parent_track_id = -1

#         # change the parent_id of the children
#         children = session.query(TrackDB).filter_by(parent_track_id=merger_to).all()

#         for child in children:
#             child.parent_track_id = merger_from

#         # delete merger_to
#         session.query(TrackDB).filter_by(track_id=merger_to).delete()

#     # check if merger_to is cut or is it the end of the track


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
    t_stop = max(cell.t for cell in query)

    return (t_stop, row_start, row_stop, column_start, column_stop)


def cut_cellsDB_mitosis(session, active_label):
    """
    Function to cut the cell of from mitotic event.
    input:
        session
        active_label - label for which the track is cut
    output:
        None
    """

    cell = (
        session.query(CellDB)
        .filter(CellDB.track_id == active_label)
        .order_by(CellDB.t)
        .first()
    )

    assert isinstance(cell, CellDB), "No cells found for the given track"

    cell.parent_id = -1

    session.commit()


def cut_cellsDB(session, active_label, current_frame, new_track):
    """
    Function to change track_id in cellsDB.
    To minimize the number of queries returns the bounding box of the track
    and the value for a new track_id.
    input:
        session
        active_label - label for which the track is cut
        current_frame - current time point
    output:
        track_bbox - bounding box of the track
    """

    # query CellDB
    # order by time
    query = (
        session.query(CellDB)
        .filter(
            and_(CellDB.track_id == active_label, CellDB.t >= current_frame)
        )
        .order_by(CellDB.t)
        .all()
    )

    assert len(query) > 0, "No cells found for the given track"

    # change the parent id of the first cell
    query[0].parent_id = -1

    # change track_ids for the cells
    for cell in query:
        cell.track_id = new_track

    # get the track_bbox
    track_bbox = _get_track_bbox(query)

    session.commit()

    return track_bbox


@njit
def _fast_forest_transverse(
    roots: List[int],
    forest: Dict[int, List[int]],
) -> Tuple[List[List[int]], List[int], List[int], List[int], List[int]]:
    """Transverse the tracks forest graph creating a distinc id to each path.

    Parameters
    ----------
    roots : List[int]
        Forest roots.
    forest : Dict[int, List[int]]
        Graph (forest).

    Returns
    -------
    Tuple[List[List[int]], List[int], List[int], List[int]]
        Sequence of paths, their respective track_id, parent_track_id and length.
    """
    track_id = 1
    paths = []
    track_ids = []  # equivalent to arange
    parent_track_ids = []
    lengths = []
    roots_list = []

    for root in roots:
        queue = [(root, NO_PARENT)]

        while queue:
            node, parent_track_id = queue.pop()
            path = _fast_path_transverse(node, track_id, queue, forest)
            paths.append(path)
            track_ids.append(track_id)
            parent_track_ids.append(parent_track_id)
            lengths.append(len(path))
            roots_list.append(root)
            track_id += 1

    return paths, track_ids, parent_track_ids, lengths, roots_list


def add_track_ids_to_tracks_df(df: pd.DataFrame) -> pd.DataFrame:
    """Adds `track_id` and `parent_track_id` columns to forest `df`.
    Each maximal path receveis a unique `track_id`.

    Parameters
    ----------
    df : pd.DataFrame
        Forest defined by the `parent_id` column and the dataframe indices.

    Returns
    -------
    pd.DataFrame
        Inplace modified input dataframe with additional columns.
    """
    assert df.shape[0] > 0

    df.index = df.index.astype(int)
    df["parent_id"] = df["parent_id"].astype(int)

    forest = create_tracks_forest(df.index.values, df["parent_id"].values)
    roots = forest.pop(NO_PARENT)

    df["track_id"] = NO_PARENT
    df["parent_track_id"] = NO_PARENT

    (
        paths,
        track_ids,
        parent_track_ids,
        lengths,
        roots_list,
    ) = _fast_forest_transverse(roots, forest)

    paths = np.concatenate(paths)
    df.loc[paths, "track_id"] = np.repeat(track_ids, lengths)
    df.loc[paths, "parent_track_id"] = np.repeat(parent_track_ids, lengths)
    df.loc[paths, "root"] = df.loc[
        np.repeat(roots_list, lengths), "track_id"
    ].tolist()

    unlabeled_tracks = df["track_id"] == NO_PARENT
    assert not np.any(
        unlabeled_tracks
    ), f"Something went wrong. Found unlabeled tracks\n{df[unlabeled_tracks]}"

    return df
