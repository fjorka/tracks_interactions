from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from numba import njit
from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Integer,
    PickleType,
)
from sqlalchemy.orm import declarative_base
from ultrack.tracks.graph import _fast_path_transverse, create_tracks_forest

# constant value to indicate it has no parent
NO_PARENT = -1
NO_SHAPE = -1

Base = declarative_base()


class CellDB(Base):
    __tablename__ = "cells"

    track_id = Column(Integer, ForeignKey("tracks.track_id"), primary_key=True)
    t = Column(Integer, primary_key=True)

    id = Column(BigInteger, unique=True)
    parent_id = Column(BigInteger, default=NO_PARENT)

    row = Column(Integer)
    col = Column(Integer)

    bbox_0 = Column(Integer, default=NO_SHAPE)
    bbox_1 = Column(Integer, default=NO_SHAPE)
    bbox_2 = Column(Integer, default=NO_SHAPE)
    bbox_3 = Column(Integer, default=NO_SHAPE)

    mask = Column(PickleType, default=NO_SHAPE)

    def __repr__(self):
        return f"{self.id} from frame {self.t} with track_id {self.track_id} at ({self.row},{self.col})"


class TrackDB(Base):
    __tablename__ = "tracks"

    track_id = Column(Integer, primary_key=True)
    parent_track_id = Column(Integer)

    # indexed to speed up queries for entire families
    root = Column(Integer, index=True)

    t_begin = Column(Integer)
    t_end = Column(Integer)

    def __repr__(self):
        return f"Track {self.track_id} from {self.t_begin} to {self.t_end}"


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
