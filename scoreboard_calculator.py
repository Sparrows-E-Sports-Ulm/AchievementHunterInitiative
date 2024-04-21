from typing import List
def calculate_scoreboard(registered_hunter : dict):
    body : List[List[str]] = []
    hunters = registered_hunter.values()
    sorted_hunters = sorted(hunters, key=lambda x: x.score, reverse=True)
    for i in range(10):
        if(i >= len(sorted_hunters)): continue
        hunter = sorted_hunters[i]
        body.insert(i, [str(i+1), str(hunter.name), str(hunter.score)])

    return body

def calculate_scoreboard_around_hunter(registered_hunter : dict, steam_id):
    body : List[List[str]] = []
    hunter = registered_hunter[steam_id]
    hunters = registered_hunter.values()
    sorted_hunters = sorted(hunters, key=lambda x: x.score, reverse=True)
    middle_index = sorted_hunters.index(hunter)
    for i in range(middle_index - 4, middle_index +4):
        if(i not in range(len(sorted_hunters))): continue
        hunter = sorted_hunters[i]
        body.insert(i, [str(i+1), str(hunter.name), str(hunter.score)])

    return body