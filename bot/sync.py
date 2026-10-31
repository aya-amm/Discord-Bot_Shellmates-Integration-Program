
def compute_changes( current: set[str], wanted: set[str], managed: set[str] ) :

    to_add =(wanted & managed) -current
    to_remove=( current & managed ) - wanted
    return (to_add , to_remove)