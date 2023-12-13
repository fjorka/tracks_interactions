import pandas as pd

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from cells_database import Base, CellDB, TrackDB

from ete3 import Tree


def add_children(node, df, n=2):

    '''
    Helper function for build_Newick_tree
    Recursively adds children to the tree from a dataframe.
    Modifies the tree in place.
    
    input:
        node - ete3.TreeNode
        df - dataframe with info about children
        n - number of the first child
    output:
        None
    '''

    # get a df with the info about children
    children = df.loc[df.parent_track_id == node.name,:]
    
    for _, row in children.iterrows():

        child_node = node.add_child(name=row['track_id'])
        child_node.add_features(num = n,
                                start = row['t_begin'], 
                                stop = row['t_end'])
        
        n += 1
        
        add_children(child_node, df, n+1)


def build_Newick_tree(engine, root_id):
    
    '''
    input:
        - root_id
        - engine
    output:
        - Newick tree to construct a graph
    '''

    # get info about the family from the database
    with Session(engine) as session:
        
        query = session.query(TrackDB).filter(TrackDB.root == root_id)
        df = pd.read_sql(query.statement, engine)

    # make sure that the root of this id exists
    assert len(df) > 0, 'No data for this root_id'

    # create tree
    tree = Tree(name = root_id)

    # add trunk
    trunk_row = df.loc[df.track_id == root_id,:]
    trunk = tree.add_child(name = root_id)
    trunk.add_features(num = 1,
                    start = trunk_row['t_begin'], 
                    stop = trunk_row['t_end'])
            

    # add children
    add_children(trunk, df)

    # return tree
    return tree







