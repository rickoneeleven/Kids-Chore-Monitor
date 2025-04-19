import os
import sys
import requests
from dotenv import load_dotenv
from todoist_api_python.api import TodoistAPI

# --- Configuration ---
# Adjust these if your project/section names are different
TARGET_PROJECT_NAME = "Kids Chores"
TARGET_SECTIONS = ["Daniel", "Sophie"]
# --- End Configuration ---

def find_and_print_ids():
    """
    Connects to Todoist, finds the specified project and sections,
    and prints their IDs.
    """
    print("Attempting to load .env file...")
    # Load environment variables from .env file in the current directory
    dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(dotenv_path):
        print(f"ERROR: .env file not found at {dotenv_path}")
        print("Please ensure the .env file exists in the same directory as this script.")
        sys.exit(1)

    load_dotenv(dotenv_path=dotenv_path)
    api_key = os.getenv("TODOIST_API_KEY")

    if not api_key:
        print("ERROR: TODOIST_API_KEY not found in the .env file.")
        print("Please ensure your Todoist API key is set in the .env file.")
        sys.exit(1)

    print("TODOIST_API_KEY loaded. Connecting to Todoist API...")

    try:
        api = TodoistAPI(api_key)

        # --- Find the Project ---
        print(f"Searching for project named: '{TARGET_PROJECT_NAME}'...")
        projects_paginator = api.get_projects() # Keep the paginator object
        target_project_id = None

        print("\n--- Iterating through Project Paginator Results ---")
        project_found = False
        # Iterate through the pages/lists yielded by the paginator
        for project_list in projects_paginator:
             print(f"DEBUG: Processing page/list element: type={type(project_list)}")
             if isinstance(project_list, list):
                  # Iterate through Project objects in the list
                 for project in project_list:
                     print(f"DEBUG: Processing project: type={type(project)}, name='{getattr(project, 'name', 'N/A')}'")
                     if hasattr(project, 'name') and project.name.strip().lower() == TARGET_PROJECT_NAME.strip().lower():
                         target_project_id = project.id
                         print(f"  SUCCESS: Found project '{project.name}' with ID: {target_project_id}")
                         project_found = True
                         break # Exit inner loop once found
             else:
                 print(f"  WARNING: Paginator yielded unexpected type: {type(project_list)}")

             if project_found:
                 break # Exit outer loop once found
        print("--- Finished Iterating Projects ---")


        if not target_project_id:
            print(f"  ERROR: Could not find project named '{TARGET_PROJECT_NAME}'.")
            # Attempt to list projects if the paginator worked somewhat normally
            try:
                all_projects = []
                for page in api.get_projects(): # Re-fetch for listing
                    if isinstance(page, list):
                        all_projects.extend(p for p in page if hasattr(p, 'name'))
                if all_projects:
                    print("  Available projects:")
                    for p in all_projects:
                        print(f"    - {p.name} (ID: {p.id})")
                else:
                    print("  Could not list available projects (paginator did not yield lists).")
            except Exception as e:
                print(f"  Could not list available projects due to error: {e}")
            sys.exit(1)

        # --- Find the Sections within the Project ---
        print(f"\nSearching for sections {TARGET_SECTIONS} within project ID {target_project_id}...")
        sections_paginator = api.get_sections(project_id=target_project_id)
        found_section_ids = {}
        all_sections_in_project = [] # Store all found sections for listing later if needed
        sections_data_found = False

        print("\n--- Iterating through Section Paginator Results ---")
        for section_list in sections_paginator:
            sections_data_found = True # Mark that we got at least one page/list
            print(f"DEBUG: Processing section page/list element: type={type(section_list)}")
            if isinstance(section_list, list):
                all_sections_in_project.extend(s for s in section_list if hasattr(s, 'name')) # Collect for listing
                for section in section_list:
                    print(f"DEBUG: Processing section: type={type(section)}, name='{getattr(section, 'name', 'N/A')}'")
                    if hasattr(section, 'name'):
                         for target_name in TARGET_SECTIONS:
                             if section.name.strip().lower() == target_name.strip().lower():
                                 found_section_ids[target_name] = section.id
                                 print(f"  SUCCESS: Found section '{section.name}' with ID: {section.id}")
            else:
                 print(f"  WARNING: Section Paginator yielded unexpected type: {type(section_list)}")

        print("--- Finished Iterating Sections ---")

        if not sections_data_found and len(TARGET_SECTIONS) > 0:
             print(f"  WARNING: No sections data yielded by paginator for project '{TARGET_PROJECT_NAME}'. Check if sections exist.")


        # --- Report Results ---
        print("\n" + "="*40)
        print(" Results - Copy these values into your .env file:")
        print("="*40)
        print(f"TODOIST_KIDS_PROJECT_ID={target_project_id}")

        all_found = True
        for target_name in TARGET_SECTIONS:
            section_id = found_section_ids.get(target_name)
            env_var_name = f"TODOIST_{target_name.upper()}_SECTION_ID"
            if section_id:
                print(f"{env_var_name}={section_id}")
            else:
                all_found = False
                print(f"# WARNING: Section '{target_name}' not found.")
                print(f"{env_var_name}=") # Print empty assignment for clarity

        print("="*40 + "\n")

        if not all_found:
             print("WARNING: Not all target sections were found. Available sections listed below:")
             if all_sections_in_project:
                 for s in all_sections_in_project:
                      print(f"    - {s.name} (ID: {s.id})")
             elif sections_data_found:
                 print("    (No sections with names found in the yielded data)")
             else:
                 print("    (No sections data retrieved)")


    # Catch specific request exceptions first
    except requests.exceptions.RequestException as error:
        print(f"Todoist API Request Error: {error}")
        sys.exit(1)
    # Catch any other unexpected errors
    except Exception as error:
        print(f"An unexpected error occurred: {error}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    find_and_print_ids()