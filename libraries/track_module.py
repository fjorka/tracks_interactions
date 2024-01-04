from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from cells_database import Base, CellDB, TrackDB


def newTrack_number(engine):

    '''
    input:
        - engine
    output:
        - number of the new track
        - in the future consider getting first unused if fast enough
    '''

    with Session(engine) as session:

        query = session.query(TrackDB.track_id).order_by(TrackDB.track_id.desc()).first()

    if query is None:
        return 0
    else:
        return query[0] + 1

def 