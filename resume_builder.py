import os
import re
import argparse
import json
import requests # For making API calls
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("API_KEY")
API_URL = os.getenv("API_URL")

def parse_obsidian_vault(master_note_path):
    """
    Recursively parses an Obsidian vault starting from a master note.
    It follows [[links]] to aggregate content from all connected notes.

    Args:
        master_note_path (str): The absolute or relative path to the main portfolio note.

    Returns:
        str: A single string containing the concatenated content of all parsed notes.
        Returns an empty string if the initial path is invalid.
    """
    vault_content = ""
    notes_to_visit = [master_note_path]
    visited_notes = set()
    base_dir = os.path.dirname(master_note_path)

    while notes_to_visit:
        current_note_path_link = notes_to_visit.pop(0)
        
        # Normalize the link to a potential file path
        # This handles links with or without the .md extension
        if current_note_path_link.endswith('.md'):
            current_note_name = os.path.basename(current_note_path_link)
        else:
            current_note_name = f"{os.path.basename(current_note_path_link)}.md"

        if current_note_name in visited_notes:
            continue

        # Search for the note file within the base directory and its subdirectories
        found_path = None
        for root, _, files in os.walk(base_dir):
            if current_note_name in files:
                found_path = os.path.join(root, current_note_name)
                break
        
        # Also check the original link in case it was a relative path from the start
        if not found_path:
            potential_path = os.path.join(base_dir, current_note_path_link)
            if not potential_path.endswith('.md'):
                potential_path += '.md'
            if os.path.exists(potential_path):
                found_path = potential_path


        if not found_path:
            print(f"Warning: Could not find linked note: {current_note_path_link}")
            continue

        try:
            with open(found_path, 'r', encoding='utf-8') as f:
                content = f.read()
                vault_content += f"\n\n--- NOTE: {os.path.basename(found_path)} ---\n\n" + content
                visited_notes.add(current_note_name)

                # Find all [[links]] in the current note's content
                links = re.findall(r'\[\[(.*?)\]\]', content)
                for link in links:
                    notes_to_visit.append(link)

        except Exception as e:
            print(f"An error occurred while reading {found_path}: {e}")

    return vault_content

def generate_resume_suggestions(portfolio_context, job_description):
    """
    Calls the Gemini API to generate resume suggestions.

    Args:
        portfolio_context (str): The aggregated content from the Obsidian vault.
        job_description (str): The text of the target job description.

    Returns:
        str: The AI-generated suggestions, or an error message.
    """
    prompt = f"""
    You are an expert career coach and resume writer. Your task is to help me tailor my resume for a specific job.

    I will provide you with two pieces of information:
    1.  **My Professional Portfolio:** This is a compilation of all my skills, experiences, projects, and education, exported from my Obsidian knowledge base.
    2.  **The Target Job Description:** This is the description of the job I am applying for.

    Based on this information, please generate a structured set of suggestions for my resume. The output should be a text file with clear, actionable advice. Follow this format exactly:

    **[Resume Summary]**
    Write a 2-3 sentence professional summary that highlights my most relevant qualifications from my portfolio that match the job description.

    **[Experience to Highlight]**
    For each of my past jobs, identify the 2-3 most relevant bullet points that align with the job description's requirements. If possible, suggest rephrasing them to include keywords from the job description.
    - **Job Title 1:**
      - Suggested Bullet Point 1
      - Suggested Bullet Point 2
    - **Job Title 2:**
      - Suggested Bullet Point 1
      - ...

    **[Projects to Feature]**
    List the top 1-2 projects from my portfolio that best demonstrate the skills needed for this job. For each project, write a brief, impactful description.

    **[Skills to Emphasize]**
    List the top 5-7 technical and soft skills from my portfolio that are most critical for this role, based on the job description.

    ---

    **My Professional Portfolio:**
    {portfolio_context}

    ---

    **The Target Job Description:**
    {job_description}
    """

    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
    }

    try:
        response = requests.post(API_URL, headers=headers, json=payload, timeout=120)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        
        result = response.json()
        
        if 'candidates' in result and result['candidates']:
            candidate = result['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content'] and candidate['content']['parts']:
                return candidate['content']['parts'][0]['text']
        
        return "Error: Could not extract valid content from API response. Full response: " + json.dumps(result)

    except requests.exceptions.RequestException as e:
        return f"An error occurred with the API request: {e}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

def main():
    """
    Main function to run the script.
    """
    parser = argparse.ArgumentParser(
        description="Generate resume suggestions based on an Obsidian portfolio and a job description."
    )
    parser.add_argument("portfolio_path", help="The file path to the master portfolio Obsidian note.")
    parser.add_argument("job_description_path", help="The file path to the .txt file containing the job description.")
    args = parser.parse_args()

    print("Step 1: Parsing your Obsidian portfolio...")
    portfolio_context = parse_obsidian_vault(args.portfolio_path)
    if not portfolio_context:
        print("Could not parse portfolio. Exiting.")
        return

    print(f"Successfully parsed {len(portfolio_context)} characters of portfolio data.")

    print("\nStep 2: Reading job description...")
    try:
        with open(args.job_description_path, 'r', encoding='utf-8') as f:
            job_description = f.read()
        print("Successfully read job description.")
    except FileNotFoundError:
        print(f"Error: Job description file not found at {args.job_description_path}")
        return
    except Exception as e:
        print(f"An error occurred while reading the job description: {e}")
        return

    print("\nStep 3: Generating tailored resume suggestions with AI...")
    suggestions = generate_resume_suggestions(portfolio_context, job_description)

    output_filename = "resume_suggestions.txt"
    try:
        with open(output_filename, 'w', encoding='utf-8') as f:
            f.write(suggestions)
        print(f"\nSuccess! Your resume suggestions have been saved to '{output_filename}'")
    except Exception as e:
        print(f"\nAn error occurred while writing the output file: {e}")
        print("\n--- AI Response ---")
        print(suggestions)


if __name__ == "__main__":
    main()

