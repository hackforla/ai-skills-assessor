#!/usr/bin/env python3
import json
from collections import defaultdict

# This script:
# - Counts the total number of unique issues in the JSON response file
# - Counts the number of comments per issue
# - Displays results as a formatted table
# Note: Not 100% if this is for "issue_comments.json" or "issue-comments.json"



def load_json_file(filepath):
    """Load and parse the JSON file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.")
        return None
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON format - {e}")
        return None


def tally_comments(data):
    """
    Tally comments per issue from the JSON data.
    
    Returns:
        dict: A dictionary with issue numbers as keys and comment counts as values
    """
    issue_comments = defaultdict(int)
    
    for comment in data:
        # Get the issue number from the comment metadata
        issue_number = comment.get('issue_number')
        
        if issue_number is not None:
            issue_comments[issue_number] += 1
    
    return dict(issue_comments)


def display_results(issue_comments):
    """Display the tally results in a formatted table."""
    # Sort issues by issue number
    sorted_issues = sorted(issue_comments.items())
    
    # Calculate statistics
    total_issues = len(sorted_issues)
    total_comments = sum(issue_comments.values())
    # avg_comments = total_comments / total_issues if total_issues > 0 else 0
    
    # Find issue with most comments
    max_issue = max(sorted_issues, key=lambda x: x[1]) if sorted_issues else (None, 0)
    
    # Print summary sentences in specified order
    print(f"The total number of issues fetched from GitHub's JSON response is: {total_issues}.")
    print(f"Total comments across all issues: {total_comments}.")
    print(f"The issue with the most comments is Issue #{max_issue[0]} with {max_issue[1]} comments.")
    print()
    
    # Print table header
    print("=" * 50)
    print(f"{'Issue Number':<20} | {'Comment Count':<20}")
    print("=" * 50)
    
    # Print each issue and its comment count
    for issue_num, comment_count in sorted_issues:
        print(f"Issue # {issue_num:<14} | {comment_count:<20}")
    
    print("=" * 50)


def main():
    """Main function to run the script."""
    # File path - adjust this to match your JSON file location
    # Using relative path from scripts/ to data/
    filepath = "../data/issue_comments.json"
    
    # Load the JSON data
    print(f"Loading data from {filepath}...")
    data = load_json_file(filepath)
    
    if data is None:
        return
    
    if not isinstance(data, list):
        print("Error: Expected JSON data to be a list of comments.")
        return
    
    print(f"Successfully loaded {len(data)} comment records.\n")
    
    # Tally comments per issue
    issue_comments = tally_comments(data)
    
    # Display results
    display_results(issue_comments)


if __name__ == "__main__":
    main()