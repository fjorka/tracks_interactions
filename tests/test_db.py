import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from tracks_interactions.db.cells_database import NO_PARENT, Base, TrackDB
from tracks_interactions.db.track_module import get_descendants, modify_trackDB


@pytest.fixture(scope="function")
def db_session():
    # Create an in-memory SQLite database
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # create a test structure
    # 1-2
    # 1-3
    # 3-4
    new_track = TrackDB(
        track_id=1, parent_track_id=NO_PARENT, root=1, t_begin=0, t_end=10
    )
    session.add(new_track)
    new_track = TrackDB(
        track_id=2, parent_track_id=1, root=1, t_begin=11, t_end=50
    )
    session.add(new_track)
    new_track = TrackDB(
        track_id=3, parent_track_id=1, root=1, t_begin=11, t_end=20
    )
    session.add(new_track)
    new_track = TrackDB(
        track_id=4, parent_track_id=3, root=1, t_begin=21, t_end=40
    )
    session.add(new_track)
    session.commit()

    yield session  # This is where the testing happens

    session.close()
    Base.metadata.drop_all(engine)


def test_starting_db(db_session):
    """Verify that the test database is set up correctly."""
    assert db_session.query(TrackDB).filter_by(track_id=1).one()


def test_adding_track(db_session):
    """Test - add a new track"""
    new_track = TrackDB(
        track_id=100, parent_track_id=None, root=0, t_begin=0, t_end=10
    )
    db_session.add(new_track)
    db_session.commit()

    # Verify the record was added
    assert db_session.query(TrackDB).filter_by(track_id=100).one()


def test_get_descendants(db_session):
    """Test checking we get correct descendants."""

    # test at the root level
    active_label = 1
    descendants = get_descendants(db_session, active_label)

    assert len(descendants) == 4

    descendants_list = [x.track_id for x in descendants]
    descendants_list.sort()
    assert descendants[0].track_id == 1
    assert descendants_list == [1, 2, 3, 4]

    # test lower in the tree
    active_label = 3
    descendants = get_descendants(db_session, active_label)

    assert len(descendants) == 2

    descendants_list = [x.track_id for x in descendants]
    descendants_list.sort()
    assert descendants[0].track_id == 3
    assert descendants_list == [3, 4]


def test_modify_track(db_session):
    """Test checking that a track is modified correctly."""

    active_label = 1
    descendants = get_descendants(db_session, active_label)

    current_frame = 5
    new_track = 100

    modify_trackDB(
        db_session, descendants, active_label, current_frame, new_track
    )

    # assert that the new track is in the database
    assert db_session.query(TrackDB).filter_by(track_id=100).one()

    # assert that the new track has expected properties
    assert db_session.query(TrackDB).filter_by(track_id=100).one().t_begin == 5
    assert db_session.query(TrackDB).filter_by(track_id=100).one().t_end == 10
    assert (
        db_session.query(TrackDB).filter_by(track_id=100).one().parent_track_id
        == -1
    )
    assert db_session.query(TrackDB).filter_by(track_id=100).one().root == 100

    # assert that the old track is modified
    assert db_session.query(TrackDB).filter_by(track_id=1).one().t_end == 4

    # assert that the children are modified
    assert db_session.query(TrackDB).filter_by(track_id=2).one().root == 100
    assert (
        db_session.query(TrackDB).filter_by(track_id=2).one().parent_track_id
        == 100
    )
    assert db_session.query(TrackDB).filter_by(track_id=3).one().root == 100
    assert (
        db_session.query(TrackDB).filter_by(track_id=3).one().parent_track_id
        == 100
    )

    # assert that the grandchildren are modified
    assert db_session.query(TrackDB).filter_by(track_id=4).one().root == 100
    assert (
        db_session.query(TrackDB).filter_by(track_id=4).one().parent_track_id
        == 3
    )
