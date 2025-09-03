#!/usr/bin/env python3
"""
Script to discover all DesignSafe projects with Hazmapper maps and generate configuration file
"""

import requests
import json
import time
from typing import List, Dict, Optional


def get_all_projects() -> List[Dict]:
    """
    Fetch all projects from DesignSafe API
    """
    base_url = "https://www.designsafe-ci.org/api/publications/v2"
    all_projects = []
    offset = 0
    limit = 100  # Use smaller batches to be respectful
    
    print("Fetching all projects from DesignSafe...")
    
    while True:
        url = f"{base_url}?offset={offset}&limit={limit}"
        print(f"Fetching projects {offset} to {offset + limit}...")
        
        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            
            projects = data.get('result', [])
            if not projects:
                break
                
            all_projects.extend(projects)
            
            # Check if we've reached the end
            if len(projects) < limit:
                break
                
            offset += limit
            
            # Be respectful with API calls
            time.sleep(0.15)
            
        except requests.RequestException as e:
            print(f"Error fetching projects at offset {offset}: {e}")
            break
    
    print(f"Total projects fetched: {len(all_projects)}")
    return all_projects


def get_project_details(project_id: str) -> Optional[Dict]:
    """
    Get detailed project information including hazmapper maps
    """
    url = f"https://www.designsafe-ci.org/api/publications/v2/{project_id}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching project {project_id}: {e}")
        return None


def extract_hazmapper_maps(project_data: Dict) -> List[Dict]:
    """
    Extract hazmapper map information from project data
    """
    hazmapper_maps = []
    
    # Check in baseProject first
    base_project = project_data.get('baseProject', {})
    maps = base_project.get('hazmapperMaps', [])
    
    # If not in baseProject, check in tree structure
    if not maps:
        tree = project_data.get('tree', {})
        if tree and 'children' in tree:
            for child in tree['children']:
                value = child.get('value', {})
                maps = value.get('hazmapperMaps', [])
                if maps:
                    break
    
    return maps


def generate_config_file(projects_with_maps: List[Dict], output_file: str = "../hazmapper_plugin/utils/maps_of_published_projects.py"):
    """
    Generate the Python configuration file
    """
    config_content = '''"""
Configuration file for predefined published Hazmapper projects
"""

# Generated automatically from DesignSafe API
predefined_published_maps = [
'''
    
    for project in projects_with_maps:
        project_id = project['projectId']
        project_title = project['title'].replace('"', '\\"')  # Escape quotes
        
        for hazmapper_map in project['hazmapperMaps']:
            uuid = hazmapper_map.get('uuid')
            if uuid:
                url = f"https://hazmapper.tacc.utexas.edu/hazmapper/project-public/{uuid}/"
                
                config_content += f'''    {{
        "url": "{url}",  # noqa: E501
        "designSafeProjectId": "{project_id}",
        "designSafeProjectName": "{project_title}",
    }},
'''
    
    config_content += ''']
'''
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(config_content)
    
    print(f"Configuration file written to: {output_file}")


def main():
    """
    Main function to orchestrate the discovery process
    """
    print("Starting DesignSafe Hazmapper discovery...")
    
    # Step 1: Get all projects
    all_projects = get_all_projects()
    
    if not all_projects:
        print("No projects found. Exiting.")
        return
    
    # Step 2: Check each project for hazmapper maps
    projects_with_maps = []
    
    print(f"\nChecking {len(all_projects)} projects for Hazmapper maps...")
    
    for i, project in enumerate(all_projects):
        project_id = project['projectId']
        print(f"Checking project {i+1}/{len(all_projects)}: {project_id}")
        
        # Get detailed project information
        project_details = get_project_details(project_id)
        
        if project_details:
            # Extract hazmapper maps
            hazmapper_maps = extract_hazmapper_maps(project_details)
            
            if hazmapper_maps:
                print(f"  ✓ Found {len(hazmapper_maps)} Hazmapper map(s)")
                projects_with_maps.append({
                    'projectId': project_id,
                    'title': project['title'],
                    'hazmapperMaps': hazmapper_maps
                })
            else:
                print(f"  - No Hazmapper maps found")
        
        # Be respectful with API calls
        time.sleep(0.15)
    
    print(f"\nFound {len(projects_with_maps)} projects with Hazmapper maps:")
    for project in projects_with_maps:
        print(f"  - {project['projectId']}: {project['title']}")
        for hm_map in project['hazmapperMaps']:
            print(f"    UUID: {hm_map.get('uuid', 'N/A')}")
    
    # Step 3: Generate configuration file
    if projects_with_maps:
        generate_config_file(projects_with_maps)
        print(f"\nGenerated configuration file with {len(projects_with_maps)} projects")
    else:
        print("\nNo projects with Hazmapper maps found.")
    
    # Save raw data as JSON for reference
    with open('projects_with_hazmapper_maps.json', 'w', encoding='utf-8') as f:
        json.dump(projects_with_maps, f, indent=2)
    print("Raw data saved to: projects_with_hazmapper_maps.json")


if __name__ == "__main__":
    main()
