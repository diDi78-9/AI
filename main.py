import requests
from fastapi import FastAPI
import fastapi
from pydantic import BaseModel
import uvicorn
import os
import signal
import logging
#import pytest

"""
By Todd Dole, Revision 1.2
Written for Hardin-Simmons CSCI-4332 Artificial Intelligence
Revision History
1.0 - API setup
1.1 - Very basic test player
1.2 - Bugs fixed and player improved, should no longer forfeit
"""


DEBUG = True
PORT = 11212
USER_NAME = "dwill"

hand = []  # list of cards in our hand
discard = []  # list of cards organized as a stack
cannot_discard = ""

# Utility function to count occurrences of each card rank in the hand
def get_of_a_kind_count(hand):
    of_a_kind_count = [0, 0, 0, 0]  # how many 1 of a kind, 2 of a kind, etc in our hand
    last_val = hand[0][0]
    count = 0
    for card in hand[1:]:
        cur_val = card[0]
        if cur_val == last_val:
            count += 1
        else:
            of_a_kind_count[count] += 1
            count = 0
        last_val = cur_val
    of_a_kind_count[count] += 1  # Need to get the last card fully processed
    return of_a_kind_count

# Function to identify runs and sets in the hand
def find_sets_and_runs(hand):
    sets = []  # list of sets (same rank)
    runs = []  # list of runs (sequences of the same suit)
    
    # Sort the hand first by rank, then by suit
    hand.sort(key=lambda card: (card[0], card[1]))
    
    # Find sets (same rank)
    rank_groups = {}
    for card in hand:
        rank = card[0]
        if rank not in rank_groups:
            rank_groups[rank] = []
        rank_groups[rank].append(card)

    # Collect sets of 3 or more of the same rank
    for rank, group in rank_groups.items():
        if len(group) >= 3:
            sets.append(group)
    
    # Find runs (sequences of the same suit)
    suit_groups = {}
    for card in hand:
        suit = card[1]
        if suit not in suit_groups:
            suit_groups[suit] = []
        suit_groups[suit].append(card)
    
    # For each suit group, look for sequences of 3 or more cards
    for suit, group in suit_groups.items():
        group.sort(key=lambda card: card[0])  # Sort by rank within each suit
        run = []
        for i, card in enumerate(group):
            if i == 0 or int(group[i][0]) == int(group[i-1][0]) + 1:  # Check for a run
                run.append(card)
            else:
                if len(run) >= 3:
                    runs.append(run)
                run = [card]
        if len(run) >= 3:
            runs.append(run)
    
    return sets, runs

# set up the FastAPI application
app = FastAPI()

# set up the API endpoints
@app.get("/")
async def root():
    ''' Root API simply confirms API is up and running.'''
    return {"status": "Running"}

# data class used to receive data from API POST
class GameInfo(BaseModel):
    game_id: str
    opponent: str
    hand: str

@app.post("/start-2p-game/")
async def start_game(game_info: GameInfo):
    ''' Game Server calls this endpoint to inform player a new game is starting. '''
    # TODO - Your code here - replace the lines below
    global hand
    global discard
    hand = game_info.hand.split(" ")
    hand.sort()
    logging.debug("2p game started, hand is "+str(hand))
    return {"status": "OK"}

# data class used to receive data from API POST
class HandInfo(BaseModel):
    hand: str

@app.post("/start-2p-hand/")
async def start_hand(hand_info: HandInfo):
    ''' Game Server calls this endpoint to inform player a new hand is starting, continuing the previous game. '''
    # TODO - Your code here
    global hand
    global discard
    discard = []
    hand = hand_info.hand.split(" ")
    hand.sort()
    logging.debug("2p hand started, hand is " + str(hand))
    return {"status": "OK"}

def process_events(event_text):
    ''' Shared function to process event text from various API endpoints '''
    # TODO - Your code here. Everything from here to end of function
    global hand
    global discard
    for event_line in event_text.splitlines():

        if ((USER_NAME + " draws") in event_line or (USER_NAME + " takes") in event_line):
            print("In draw, hand is "+str(hand))
            print("Drew "+event_line.split(" ")[-1])
            hand.append(event_line.split(" ")[-1])
            hand.sort()
            print("Hand is now "+str(hand))
            logging.debug("Drew a "+event_line.split(" ")[-1]+", hand is now: "+str(hand))
        if ("discards" in event_line):  # add a card to discard pile
            discard.insert(0, event_line.split(" ")[-1])
        if ("takes" in event_line): # remove a card from discard pile
            discard.pop(0)
        if " Ends:" in event_line:
            print(event_line)

# data class used to receive data from API POST
class UpdateInfo(BaseModel):
    game_id: str
    event: str

@app.post("/update-2p-game/")
async def update_2p_game(update_info: UpdateInfo):
    '''
        Game Server calls this endpoint to update player on game status and other players' moves.
        Typically only called at the end of game.
    '''
    # TODO - Your code here - update this section if you want
    process_events(update_info.event)
    print(update_info.event)
    return {"status": "OK"}

def get_count(hand,card):
    count = 0
    for c in hand:
        if c == card:
            count += 1
    return hand.count(card)

@app.post("/draw/")
async def draw(update_info: UpdateInfo):
    ''' Game Server calls this endpoint to start player's turn with draw from discard pile or draw pile.'''
    global cannot_discard
    # TODO - Your code here - everything from here to end of function
    process_events(update_info.event)
    if len(discard)<1: # If the discard pile is empty, draw from stock
        cannot_discard = ""
        return {"play": "draw stock"}
    if any(discard[0][0] in s for s in hand):
        cannot_discard = discard[0] # if our hand contains a matching card, take it
        return {"play": "draw discard"}
    return {"play": "draw stock"} # Otherwise, draw from stock

@app.post("/lay-down/")
async def lay_down(update_info: UpdateInfo):
    ''' Game Server calls this endpoint to conclude player's turn with melding and/or discard.'''
    # Global variables
    global hand
    global discard
    global cannot_discard
    
    # Process events for the current game
    process_events(update_info.event)
    
    # Get the count of different ranks in hand
    of_a_kind_count = get_of_a_kind_count(hand)
    
    # If there are too many unmeldable cards, we need to discard
    if (of_a_kind_count[0] + (of_a_kind_count[1] * 2)) > 1:
        logging.debug("Need to discard unmeldable cards.")
        
        # Discard the highest card if we have 1 of a kind
        if of_a_kind_count[0] > 0:
            logging.debug("Discarding a single card.")
            
            if hand[-1][0] != hand[-2][0]:
                # Discard the highest single card
                discard_string = " discard " + hand.pop()
                logging.debug(f"Discarded {discard_string}")
                return {"play": discard_string}
            
            # If the last two cards are identical, discard the highest single card
            for i in range(len(hand)-2, -1, -1):
                if i == 0 or hand[i][0] != hand[i-1][0] and hand[i][0] != hand[i+1][0]:
                    discard_string = " discard " + hand.pop(i)
                    logging.debug(f"Discarded {discard_string}")
                    return {"play": discard_string}

        # If we have a 2 of a kind, discard one of them
        elif of_a_kind_count[1] >= 1:
            logging.debug("Discarding two of a kind.")
            
            for i in range(len(hand)-1, -1, -1):
                if hand[i] != cannot_discard and get_count(hand, hand[i]) == 2:
                    discard_string = " discard " + hand.pop(i)
                    logging.debug(f"Discarded {discard_string}")
                    return {"play": discard_string}

            discard_string = " discard " + hand.pop()  # Fallback discard
            logging.debug(f"Discarded {discard_string}")
            return {"play": discard_string}
    
    # We should be able to meld
    meld_string = ""
    
    # Find the sets and runs from hand
    sets, runs = find_sets_and_runs(hand)
    
    # Construct the meld string
    for s in sets:
        meld_string += "meld " + " ".join(s) + " "
    for r in runs:
        meld_string += "meld " + " ".join(r) + " "
    
    # Handle discard if necessary
    if meld_string.strip():  # If we melded something, we may not need to discard
        discard_string = ""
    else:
        # If no melds, then discard one card
        discard_string = " discard " + hand.pop()
    
    play_string = meld_string.strip() + discard_string
    logging.debug(f"Playing: {play_string}")
    
    # Return the play action
    return {"play": play_string}

 
@app.get("/shutdown")
async def shutdown_API():
    ''' Game Server calls this endpoint to shut down the player's client after testing is completed.  Only used if DEBUG is True. '''
    os.kill(os.getpid(), signal.SIGTERM)
    logging.debug("Player client shutting down...")
    return fastapi.Response(status_code=200, content='Server shutting down...')

''' Main code here - registers the player with the server via API call, and then launches the API to receive game information '''
if __name__ == "__main__":

    if (DEBUG):
        url = "http://127.0.0.1:16200/test"

        # TODO - Change logging.basicConfig if you want
        logging.basicConfig(filename="RummyPlayer.log", format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',level=logging.DEBUG)
    else:
        url = "http://127.0.0.1:16200/register"
        # TODO - Change logging.basicConfig if you want
        logging.basicConfig(filename="RummyPlayer.log", format='%(asctime)s - %(levelname)s - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S',level=logging.WARNING)

    payload = {
        "name": USER_NAME,
        "address": "127.0.0.1",
        "port": str(PORT)
    }

    try:
        # Call the URL to register client with the game server
        response = requests.post(url, json=payload)
    except Exception as e:
        print("Failed to connect to server.  Please contact Mr. Dole.")
        exit(1)

    if response.status_code == 200:
        print("Request succeeded.")
        print("Response:", response.json())  # or response.text
    else:
        print("Request failed with status:", response.status_code)
        print("Response:", response.text)
        exit(1)

    # run the client API using uvicorn
    uvicorn.run(app, host="127.0.0.1", port=PORT)
