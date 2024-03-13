from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from numba import njit
from ultrack.tracks.graph import _create_tracks_forest, _fast_path_transverse

from tracks_interactions.db.db_model import NO_PARENT


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

    forest = _create_tracks_forest(df.index.values, df["parent_id"].values)
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
