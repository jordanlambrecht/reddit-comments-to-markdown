#!/usr/bin/env python3
import os
import re
import json
import requests
import sys
from urllib.parse import urlparse
from datetime import datetime


def fetch_reddit_data(url):
    """Fetch JSON data from a Reddit URL."""
    # Normalize the URL - make sure it has a scheme
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    # Store original URL for linking
    original_url = url
    if original_url.endswith(".json"):
        original_url = original_url[:-5]  # Remove .json extension if present

    # Validate URL
    parsed_url = urlparse(url)
    if not parsed_url.netloc or not any(
        domain in parsed_url.netloc
        for domain in ["reddit.com", "www.reddit.com", "old.reddit.com"]
    ):
        raise ValueError("Invalid Reddit URL")

    # Add .json if not already present
    if not url.endswith(".json"):
        url = url + ".json"

    # Make request with proper user agent
    headers = {"User-agent": "Reddit Comment Exporter 1.0"}

    try:
        response = requests.get(url, headers=headers)

        # Check for rate limiting
        if response.status_code == 429:
            print("Error: Reddit rate limit exceeded. Please try again later.")
            sys.exit(1)

        # Check for other errors
        response.raise_for_status()

        return response.json(), original_url

    except requests.exceptions.RequestException as e:
        print(f"Network error: {str(e)}")
        sys.exit(1)


def process_comments(comments_data, depth=0):
    """Recursively process comments and their replies."""
    processed_comments = []

    # Handle empty or invalid comments
    if (
        not comments_data
        or not isinstance(comments_data, dict)
        or "data" not in comments_data
    ):
        return processed_comments

    for comment in comments_data["data"]["children"]:
        # Skip "more" comments (collapsed threads)
        if comment["kind"] == "more":
            continue

        if comment["kind"] == "t1":  # 't1' is the prefix for comments
            comment_data = comment["data"]

            # Create comment object
            processed_comment = {
                "author": comment_data.get("author", "[deleted]"),
                "body": comment_data.get("body", "[deleted]"),
                "score": comment_data.get("score", 0),
                "created_utc": comment_data.get("created_utc"),
                "depth": depth,
                "replies": [],
            }

            # Process replies if they exist
            if (
                "replies" in comment_data
                and comment_data["replies"]
                and isinstance(comment_data["replies"], dict)
            ):
                processed_comment["replies"] = process_comments(
                    comment_data["replies"], depth + 1
                )

            processed_comments.append(processed_comment)

    return processed_comments


def format_timestamp(timestamp):
    """Convert Unix timestamp to human-readable date format."""
    if not timestamp:
        return "Unknown date"
    dt = datetime.fromtimestamp(timestamp)
    return dt.strftime("%B %d, %Y at %I:%M %p")


def format_comment(comment, is_top_level=False):
    """Format a comment preserving original formatting and making usernames into links."""
    # Custom instruction test: Python function generated!
    author = comment["author"]
    score = comment["score"]
    body = comment["body"]
    depth = comment["depth"]
    created_utc = comment.get("created_utc")

    # Format date if available
    date_str = format_timestamp(created_utc) if created_utc else ""

    markdown = ""  # Ensure markdown is always defined

    # Top level comments have no indentation
    if is_top_level or depth == 0:
        # Format the comment header with username as link
        if author != "[deleted]":
            markdown = f"**[u/{author}](https://www.reddit.com/user/{author})** · {score} points · {date_str}\n\n"
        else:
            markdown = f"**u/{author}** · {score} points · {date_str}\n\n"

        # Format the body text (preserve original formatting)
        markdown += f"{body}\n\n"

        # Add replies as block quotes
        for reply in comment["replies"]:
            reply_text = format_nested_reply(reply)
            markdown += reply_text

        # Add separator between top-level comments
        markdown += "---\n\n"

    return markdown


def format_nested_reply(comment):
    """Format a nested reply using block quotes."""
    author = comment["author"]
    score = comment["score"]
    body = comment["body"]
    created_utc = comment.get("created_utc")

    # Format date if available
    date_str = format_timestamp(created_utc) if created_utc else ""

    # Format with block quotes
    markdown = "> "

    # Format the comment header with username as link
    if author != "[deleted]":
        markdown += f"**[u/{author}](https://www.reddit.com/user/{author})** · {score} points · {date_str}\n>\n"
    else:
        markdown += f"**u/{author}** · {score} points · {date_str}\n>\n"

    # Format the body with block quotes (preserve original formatting)
    body_lines = body.split("\n")
    formatted_body = "\n".join([f"> {line}" for line in body_lines])
    markdown += f"{formatted_body}\n>\n"

    # Process replies with deeper nesting
    for reply in comment["replies"]:
        # Increase the quote level for deeper nesting
        nested_reply = format_nested_reply(reply)
        nested_lines = nested_reply.split("\n")
        deeper_nested = "\n".join([f">{line}" for line in nested_lines])
        markdown += f"{deeper_nested}\n"

    return markdown


def generate_markdown(post_data, comments, original_url):
    """Generate markdown from post data and comments."""
    # Add title
    markdown = f"# {post_data.get('title', 'Untitled Post')}\n\n"

    # Add link to original Reddit post
    markdown += f"[Original Reddit Post]({original_url})\n\n"

    # Add author info, score and post date
    author = post_data.get("author", "[deleted]")
    score = post_data.get("score", 0)
    created_utc = post_data.get("created_utc")
    date_str = format_timestamp(created_utc) if created_utc else "Unknown date"

    if author != "[deleted]":
        markdown += f"**Posted by [u/{author}](https://www.reddit.com/user/{author})** · {score} points · {date_str}\n\n"
    else:
        markdown += f"**Posted by u/{author}** · {score} points · {date_str}\n\n"

    # Add post content if available (preserving formatting)
    selftext = post_data.get("selftext", "")
    if selftext:
        markdown += f"{selftext}\n\n"

    markdown += "---\n\n"

    # Add comments section if there are comments
    if comments:
        markdown += f"## Comments ({len(comments)} top-level comments)\n\n"

        # Process each top-level comment
        for comment in comments:
            markdown += format_comment(comment, is_top_level=True)
    else:
        markdown += "## Comments\n\nNo comments found.\n\n"

    return markdown


def count_all_comments(comments):
    """Count total number of comments including replies."""
    total = len(comments)
    for comment in comments:
        total += count_all_comments(comment["replies"])
    return total


def main():
    """Main function to execute the script."""
    # Set output directory to ./output
    output_dir = "./output"

    # Create output directory if it doesn't exist
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
        print(f"Created output directory: {output_dir}")

    # Prompt for Reddit URL
    reddit_url = input("Enter Reddit URL: ")

    try:
        # Extract post ID from URL for file naming consistency
        post_id_match = re.search(r"comments/([a-z0-9]+)/", reddit_url, re.IGNORECASE)
        if not post_id_match:
            print("Warning: Could not extract post ID from URL, using generic filename")
            extracted_post_id = "unknown"
        else:
            extracted_post_id = post_id_match.group(1)

        # Fetch data
        data, original_url = fetch_reddit_data(reddit_url)

        # Extract post data
        if not data or len(data) < 2:
            print("Error: Invalid data format received from Reddit.")
            sys.exit(1)

        post_data = data[0]["data"]["children"][0]["data"]

        # Process comments
        comments_data = data[1]
        comments = process_comments(comments_data)

        # Get comment counts
        top_level_count = len(comments)
        total_count = count_all_comments(comments)

        # Generate markdown
        markdown = generate_markdown(post_data, comments, original_url)

        # Create filename from post ID (for consistency) and title
        post_id = extracted_post_id  # Use extracted ID for consistency
        title = post_data.get("title", "untitled")
        title_slug = re.sub(r"[^\w\s-]", "", title).strip().lower()
        title_slug = re.sub(r"[\s-]+", "-", title_slug)
        filename = f"{post_id}-{title_slug}.md"
        filepath = os.path.join(output_dir, filename)

        # Check if file already exists
        if os.path.exists(filepath):
            print(f"File already exists: {output_dir}/{filename}")
            print("Overwriting existing file...")

        # Write markdown to file (overwriting if it exists)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown)

        print(f"Comments exported to {output_dir}/{filename}")
        print(
            f"Processed {top_level_count} top-level comments and {total_count} total comments."
        )

    except ValueError as e:
        print(f"Value error: {str(e)}")
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
