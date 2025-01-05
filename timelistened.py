import json
from collections import defaultdict
from typing import List, Dict, Tuple
from datetime import datetime
import glob
import os

def get_date_range(data_entries: List[dict]) -> Tuple[datetime, datetime]:
    """Get the earliest and latest dates in the dataset"""
    dates = [datetime.strptime(entry['ts'], "%Y-%m-%dT%H:%M:%SZ") 
            for entry in data_entries if 'ts' in entry]
    return min(dates), max(dates)

def get_user_date_range() -> Tuple[datetime, datetime]:
    """Get date range from user input"""
    print("\nEnter dates in format YYYY-MM-DD")
    while True:
        try:
            from_date = input("From date (or press Enter for earliest): ").strip()
            to_date = input("To date (or press Enter for latest): ").strip()
            
            if from_date:
                from_date = datetime.strptime(from_date, "%Y-%m-%d")
            if to_date:
                to_date = datetime.strptime(to_date, "%Y-%m-%d")
                # Set time to end of day
                to_date = to_date.replace(hour=23, minute=59, second=59)
            
            return from_date, to_date
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD format.")

def get_user_limits(total_songs: int, total_artists: int) -> Tuple[int, int]:
    """
    Get user input for display limits
    
    Args:
        total_songs: Total number of songs in rankings
        total_artists: Total number of artists in rankings
    
    Returns:
        Tuple of (song_limit, artist_limit)
    """
    while True:
        try:
            print("\nEnter display limits (0 for all):")
            song_limit = int(input(f"Number of songs to display (0-{total_songs}): "))
            artist_limit = int(input(f"Number of artists to display (0-{total_artists}): "))
            
            # Validate inputs
            if song_limit < 0 or artist_limit < 0:
                print("Please enter non-negative numbers.")
                continue
                
            # Convert 0 to None for no limit
            song_limit = None if song_limit == 0 else song_limit
            artist_limit = None if artist_limit == 0 else artist_limit
            
            # Ensure limits don't exceed totals
            if song_limit and song_limit > total_songs:
                print(f"Song limit exceeds total songs. Setting to maximum ({total_songs})")
                song_limit = total_songs
            if artist_limit and artist_limit > total_artists:
                print(f"Artist limit exceeds total artists. Setting to maximum ({total_artists})")
                artist_limit = total_artists
                
            return song_limit, artist_limit
            
        except ValueError:
            print("Please enter valid numbers.")


def process_streaming_files(file_paths: List[str]) -> Tuple[List[Tuple[str, str, float]], Dict[int, float]]:
    # Use defaultdict to automatically handle new songs and years
    song_playtime: Dict[Tuple[str, str], int] = defaultdict(int)
    yearly_playtime: Dict[int, int] = defaultdict(int)
    
    # First, get all data and find date range
    all_data = []
    for file_path in file_paths:
        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                data = json.load(file)
                all_data.extend(data)
        except json.JSONDecodeError:
            print(f"Error reading {file_path}: Invalid JSON format")
        except Exception as e:
            print(f"Error processing {file_path}: {str(e)}")
    
    # Get dataset date range
    earliest_date, latest_date = get_date_range(all_data)
    print(f"\nDataset range: {earliest_date.date()} to {latest_date.date()}")
    
    # Get user's desired date range
    user_from_date, user_to_date = get_user_date_range()
    
    # If dates are empty or out of range, use dataset limits
    if not user_from_date or user_from_date < earliest_date:
        user_from_date = earliest_date
        print(f"Using earliest available date: {earliest_date.date()}")
    if not user_to_date or user_to_date > latest_date:
        user_to_date = latest_date
        print(f"Using latest available date: {latest_date.date()}")
    
    print(f"\nAnalyzing data from {user_from_date.date()} to {user_to_date.date()}")
    
    # Process the filtered data
    for entry in all_data:
        try:
            if ('ms_played' in entry and 
                'master_metadata_track_name' in entry and 
                'master_metadata_album_artist_name' in entry and
                'ts' in entry):
                
                entry_date = datetime.strptime(entry['ts'], "%Y-%m-%dT%H:%M:%SZ")
                
                # Skip if outside selected date range
                if entry_date < user_from_date or entry_date > user_to_date:
                    continue
                
                track_name = entry['master_metadata_track_name']
                artist_name = entry['master_metadata_album_artist_name']
                ms_played = entry['ms_played']
                
                # Add to yearly total
                year = entry_date.year
                yearly_playtime[year] += ms_played
                
                if track_name and artist_name:  # Only process if both names are not None
                    song_playtime[(track_name, artist_name)] += ms_played
                    
        except Exception as e:
            print(f"Error processing entry: {str(e)}")

    # Convert milliseconds to minutes and sort by play time (descending)
    ranked_songs = [
        (song[0], song[1], ms_played / 60000)  # (track_name, artist_name, minutes)
        for song, ms_played in song_playtime.items()
    ]
    ranked_songs.sort(key=lambda x: x[2], reverse=True)
    
    # Convert yearly playtime from milliseconds to hours
    yearly_playtime_hours = {
        year: ms_played / (1000 * 60 * 60)  # Convert ms to hours
        for year, ms_played in yearly_playtime.items()
    }
    
    return ranked_songs, yearly_playtime_hours

def print_rankings(rankings: List[Tuple[str, str, float]], limit: int = None):
    print(f"\nTop {limit if limit else 'All'} Songs by Total Listen Time (in minutes):")
    for index, (song, artist, minutes) in enumerate(rankings[:limit], 1):
        print(f"{index}. {song} - {artist}: {round(minutes, 2)} minutes")

def print_artist_rankings(rankings: List[Tuple[str, str, float]], limit: int = None):
    # Create dictionaries to store data per artist
    artist_playtime: Dict[str, float] = defaultdict(float)
    artist_positions: Dict[str, List[int]] = defaultdict(list)
    
    # Sum up minutes and collect positions for each artist
    for position, (_, artist, minutes) in enumerate(rankings, 1):
        artist_playtime[artist] += minutes
        artist_positions[artist].append(position)
    
    # Calculate statistics for each artist
    artist_stats = []
    for artist in artist_playtime.keys():
        total_minutes = artist_playtime[artist]
        
        # Sort positions and take top 5 (or all if less than 5)
        sorted_positions = sorted(artist_positions[artist])
        num_songs = len(sorted_positions)
        top_count = min(5, num_songs)  # Take either 5 songs or all songs if less than 5
        top_positions = sorted_positions[:top_count]
        
        # Calculate average position using selected songs
        avg_position = sum(top_positions) / len(top_positions)
        
        artist_stats.append((
            artist,
            total_minutes,
            avg_position,
            num_songs,
            top_count
        ))
    
    # Create two sorted lists - one by playtime, one by average position
    playtime_sorted = sorted(artist_stats, key=lambda x: x[1], reverse=True)
    position_sorted = sorted(artist_stats, key=lambda x: x[2])  # Lower position is better
    
    # Print rankings by playtime
    print(f"\nTop {limit if limit else 'All'} Artists by Total Listen Time:")
    for index, (artist, minutes, avg_pos, song_count, top_count) in enumerate(playtime_sorted[:limit], 1):
        hours = minutes / 60
        print(f"{index}. {artist}: {round(hours, 2)} hours ({round(minutes, 2)} minutes)")
        print(f"   Average position of top {top_count} songs: {round(avg_pos, 1)} (out of {song_count} total songs)")
    
    # Print rankings by average position
    print(f"\nTop {limit if limit else 'All'} Artists by Average Song Position (of their top 5 songs):")
    for index, (artist, minutes, avg_pos, song_count, top_count) in enumerate(position_sorted[:limit], 1):
        hours = minutes / 60
        print(f"{index}. {artist}: Average position {round(avg_pos, 1)} (top {top_count} of {song_count} songs)   Total listening time: {round(hours, 2)} hours")





def print_yearly_stats(yearly_stats: Dict[int, float]):
    print("\nYearly Listening Statistics:")
    for year in sorted(yearly_stats.keys()):
        print(f"{year}: {round(yearly_stats[year], 2)} hours")

# Specify your JSON files here
files_to_process = [
    "Streaming_History_Audio_2020-2022_0.json",
    "Streaming_History_Audio_2022_1.json",
    "Streaming_History_Audio_2022-2023_2.json",
    "Streaming_History_Audio_2023_3.json",
    "Streaming_History_Audio_2023_4.json",
    "Streaming_History_Audio_2023-2024_5.json",
    "Streaming_History_Audio_2024_6.json",
    "Streaming_History_Audio_2024-2025_7.json"
]

# Process the files and get rankings and yearly stats
rankings, yearly_stats = process_streaming_files(files_to_process)


def display_stats(rankings: List[Tuple[str, str, float]]):
    """
    Display statistics with user-defined limits
    
    Args:
        rankings: List of (song, artist, minutes) tuples
    """
    # Get total counts
    total_songs = len(rankings)
    total_artists = len(set(artist for _, artist, _ in rankings))
    
    # Get user input for limits
    song_limit, artist_limit = get_user_limits(total_songs, total_artists)
    
    # Display stats with user-defined limits
    print_rankings(rankings, song_limit)
    print_artist_rankings(rankings, artist_limit)
    print_yearly_stats(yearly_stats)


display_stats(rankings)
