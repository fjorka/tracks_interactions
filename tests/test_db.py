import pytest
from sqlalchemy import MetaData, create_engine, inspect
from sqlalchemy.orm import sessionmaker

from tracks_interactions.db.db_functions import (
    cut_cellsDB,
    cut_cellsDB_mitosis,
    cut_trackDB,
    get_descendants,
    newTrack_number,
)

# merge_trackDB,
from tracks_interactions.db.db_model import NO_PARENT, CellDB, TrackDB


@pytest.fixture(scope="function")
def db_session():
    # see "./tests/fixtures/test_database_content.PNG" for a visual representation of copied part of the test database
    test_db_path = r"./tests/fixtures/db_2tables_test.db"
    original_engine = create_engine(f"sqlite:///{test_db_path}")
    original_metadata = MetaData()
    original_metadata.reflect(bind=original_engine)

    # Create an in-memory SQLite database
    memory_engine = create_engine("sqlite:///:memory:")
    original_metadata.create_all(memory_engine)

    # Open sessions
    OriginalSession = sessionmaker(bind=original_engine)
    MemorySession = sessionmaker(bind=memory_engine)

    original_session = OriginalSession()
    memory_session = MemorySession()

    # Copy tables
    cells = original_session.query(CellDB).all()
    tracks = original_session.query(TrackDB).all()

    for cell in cells:
        # Create a new instance of CellDB
        new_cell = CellDB()

        # Deep copy
        for key, value in inspect(cell).attrs.items():
            setattr(new_cell, key, value.value)

        memory_session.add(new_cell)

    for track in tracks:
        # Create a new instance of TrackDB
        new_track = TrackDB()

        # Deep copy
        for key, value in inspect(track).attrs.items():
            setattr(new_track, key, value.value)

        memory_session.add(new_track)

    original_session.close()

    # add additional tracks (no cells)
    # 1 (0 - 10)
    # 1-2 (11 - 50)
    # 1-3 (11 - 20)
    # 3-4 (21 - 40)
    # 5 unconnected starts (41 - 45)
    new_track = TrackDB(
        track_id=1, parent_track_id=NO_PARENT, root=1, t_begin=0, t_end=10
    )
    memory_session.add(new_track)
    new_track = TrackDB(
        track_id=2, parent_track_id=1, root=1, t_begin=11, t_end=50
    )
    memory_session.add(new_track)
    new_track = TrackDB(
        track_id=3, parent_track_id=1, root=1, t_begin=11, t_end=20
    )
    memory_session.add(new_track)
    new_track = TrackDB(
        track_id=4, parent_track_id=3, root=1, t_begin=21, t_end=40
    )
    memory_session.add(new_track)

    # freely floating track
    new_track = TrackDB(
        track_id=5, parent_track_id=-1, root=5, t_begin=41, t_end=45
    )
    memory_session.add(new_track)

    memory_session.commit()

    yield memory_session  # This is where the testing happens

    memory_session.close()


def test_starting_db(db_session):
    """Verify that the test database is set up correctly."""
    assert db_session.query(TrackDB).filter_by(track_id=15854).one()


def test_adding_track(db_session):
    """Test - add a new track"""
    new_track = TrackDB(
        track_id=100, parent_track_id=None, root=0, t_begin=0, t_end=10
    )
    db_session.add(new_track)
    db_session.commit()

    # Verify the record was added
    assert db_session.query(TrackDB).filter_by(track_id=100).one()


def test_newTrack_number(db_session):
    """Test - getting a new track number."""

    new_track = newTrack_number(db_session)
    assert new_track == 17182

    new_track_number = 6e10
    new_track = TrackDB(
        track_id=new_track_number,
        parent_track_id=None,
        root=0,
        t_begin=0,
        t_end=10,
    )
    db_session.add(new_track)
    db_session.commit()

    new_track = newTrack_number(db_session)
    assert new_track == new_track_number + 1


def test_get_descendants(db_session):
    """Test checking we get correct descendants."""

    # test at the root level
    active_label = 15854
    descendants = get_descendants(db_session, active_label)

    assert len(descendants) == 3

    descendants_list = [x.track_id for x in descendants]
    descendants_list.sort()
    assert descendants[0].track_id == active_label
    assert descendants_list == [15854, 15855, 15856]

    # test lower in the tree
    active_label = 3
    descendants = get_descendants(db_session, active_label)

    assert len(descendants) == 2

    descendants_list = [x.track_id for x in descendants]
    descendants_list.sort()
    assert descendants[0].track_id == active_label
    assert descendants_list == [3, 4]


def test_cut_trackDB(db_session):
    """Test checking that a track is modified correctly."""

    active_label = 1
    current_frame = 5

    new_track_expected = newTrack_number(db_session)

    mitosis, new_track = cut_trackDB(db_session, active_label, current_frame)

    # assert expected output of the function
    assert mitosis is False
    assert new_track == new_track_expected

    # assert that the new track is in the database
    assert db_session.query(TrackDB).filter_by(track_id=new_track).one()

    # assert that the new track has expected properties
    assert (
        db_session.query(TrackDB).filter_by(track_id=new_track).one().t_begin
        == 5
    )
    assert (
        db_session.query(TrackDB).filter_by(track_id=new_track).one().t_end
        == 10
    )
    assert (
        db_session.query(TrackDB)
        .filter_by(track_id=new_track)
        .one()
        .parent_track_id
        == -1
    )
    assert (
        db_session.query(TrackDB).filter_by(track_id=new_track).one().root
        == new_track
    )

    # assert that the old track is modified
    assert db_session.query(TrackDB).filter_by(track_id=1).one().t_end == 4

    # assert that the children are modified
    assert (
        db_session.query(TrackDB).filter_by(track_id=2).one().root == new_track
    )
    assert (
        db_session.query(TrackDB).filter_by(track_id=2).one().parent_track_id
        == new_track
    )
    assert (
        db_session.query(TrackDB).filter_by(track_id=3).one().root == new_track
    )
    assert (
        db_session.query(TrackDB).filter_by(track_id=3).one().parent_track_id
        == new_track
    )

    # assert that the grandchildren are modified
    assert (
        db_session.query(TrackDB).filter_by(track_id=4).one().root == new_track
    )
    assert (
        db_session.query(TrackDB).filter_by(track_id=4).one().parent_track_id
        == 3
    )


def test_cut_trackDB_mitosis(db_session):
    """
    Test cut_TrackDB function when cutting from mitosis.
    """

    active_label = 17175

    record = db_session.query(TrackDB).filter_by(track_id=active_label).one()

    t_begin_org = record.t_begin
    t_end_org = record.t_end

    new_track_hypothesis = newTrack_number(db_session)

    mitosis, new_track = cut_trackDB(db_session, active_label, t_begin_org)

    # assert expected output of the function
    assert mitosis is True
    assert new_track is None

    # assert that the active label track is in the database
    assert db_session.query(TrackDB).filter_by(track_id=active_label).one()

    # assert that the changed track has expected properties
    assert (
        db_session.query(TrackDB)
        .filter_by(track_id=active_label)
        .one()
        .t_begin
        == t_begin_org
    )
    assert (
        db_session.query(TrackDB).filter_by(track_id=active_label).one().t_end
        == t_end_org
    )
    assert (
        db_session.query(TrackDB)
        .filter_by(track_id=active_label)
        .one()
        .parent_track_id
        == -1
    )
    assert (
        db_session.query(TrackDB).filter_by(track_id=active_label).one().root
        == active_label
    )

    # assert that the new track was not created
    assert (
        len(
            db_session.query(TrackDB)
            .filter_by(track_id=new_track_hypothesis)
            .all()
        )
        == 0
    )


def test_cut_cellsDB(db_session):
    """Test checking whether the cut_cellsDB function works correctly."""

    active_label = 15854

    # check how long the track is before the cut
    org_stop = (
        db_session.query(TrackDB).filter_by(track_id=active_label).one().t_end
    )

    current_frame = 5
    new_track = 100

    _ = cut_cellsDB(db_session, active_label, current_frame, new_track)

    # assert that there are only 5 objects of old track in the cell table after cut
    assert (
        len(db_session.query(CellDB).filter_by(track_id=active_label).all())
        == current_frame
    )

    # assert that there is expected number of objects in new track
    assert len(
        db_session.query(CellDB).filter_by(track_id=new_track).all()
    ) == (org_stop - current_frame + 1)

    # assert that the first object in a new track doesn't have a parent
    assert (
        db_session.query(CellDB)
        .filter_by(track_id=new_track)
        .filter(CellDB.t == current_frame)
        .one()
        .parent_id
        == -1
    )

    # assert that parents are not changed on the original track
    assert (
        db_session.query(CellDB)
        .filter_by(track_id=active_label)
        .filter(CellDB.t == current_frame - 1)
        .one()
        .parent_id
        == db_session.query(CellDB)
        .filter_by(track_id=active_label)
        .filter(CellDB.t == current_frame - 2)
        .one()
        .id
    )


def test_cut_cellsDB_mitosis(db_session):
    """Test checking whether the cut_cellsDB function works correctly."""

    active_label = 15856

    # check how long the track is before the cut
    records_org = (
        db_session.query(CellDB)
        .filter_by(track_id=active_label)
        .order_by(CellDB.t)
        .all()
    )

    cut_cellsDB_mitosis(db_session, active_label)

    records = (
        db_session.query(CellDB)
        .filter_by(track_id=active_label)
        .order_by(CellDB.t)
        .all()
    )

    assert records[0].parent_id == -1
    assert records[1].parent_id == records[0].id
    assert records[1] == records_org[1]


# def test_merge_trackDB_freely_floating(db_session):
#     """Test checking if a freely floating track can be merged.
#     No descendants on neither side."""

#     merger_to = 4
#     merger_from = 5
#     current_frame = 41

#     org_start  = db_session.query(TrackDB).filter_by(track_id=merger_to).one().t_begin
#     org_stop = db_session.query(TrackDB).filter_by(track_id=merger_from).one().t_end
#     org_parent = db_session.query(TrackDB).filter_by(track_id=merger_to).one().parent_track_id
#     org_root = db_session.query(TrackDB).filter_by(track_id=merger_to).one().root

#     merge_trackDB(
#         db_session, merger_from, merger_to, current_frame
#     )

#     # assert that the merger from track is not in the database
#     assert len(db_session.query(TrackDB).filter_by(track_id=merger_from).all()) == 0

#     # assert that the merger to has expected properties
#     assert db_session.query(TrackDB).filter_by(track_id=merger_to).one().t_begin == org_start
#     assert db_session.query(TrackDB).filter_by(track_id=merger_to).one().t_end == org_stop
#     assert db_session.query(TrackDB).filter_by(track_id=merger_to).one().parent_track_id == org_parent
#     assert db_session.query(TrackDB).filter_by(track_id=merger_to).one().root == org_root
