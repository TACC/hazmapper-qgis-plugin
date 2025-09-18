#!/usr/bin/env python3
# noqa: E501
"""
Script to discover all DesignSafe projects with Hazmapper maps and generate configuration file
"""

import argparse
import json
import os
import requests
import time
from typing import List, Dict, Optional

# Configuration
SLEEP_TIME = 0.1  # Seconds to sleep between API calls


def get_all_projects(short_version: bool = False) -> List[Dict]:
    """
    Fetch all projects from DesignSafe API
    """
    base_url = "https://www.designsafe-ci.org/api/publications/v2"
    all_projects = []
    offset = 0
    limit = 100  # Use smaller batches to be respectful
    max_projects = 100 if short_version else None

    print(
        f"Fetching projects from "
        f"DesignSafe{' (short version - 100 projects)' if short_version else ''}..."
    )

    while True:
        url = f"{base_url}?offset={offset}&limit={limit}"
        print(f"Fetching projects {offset} to {offset + limit}...")

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()

            projects = data.get("result", [])
            if not projects:
                break

            all_projects.extend(projects)

            # Check if we've reached the max for short version
            if max_projects and len(all_projects) >= max_projects:
                all_projects = all_projects[:max_projects]
                break

            # Check if we've reached the end
            if len(projects) < limit:
                break

            offset += limit

            # Be respectful with API calls
            time.sleep(SLEEP_TIME)

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


def check_hazmapper_project(uuid: str) -> Dict:
    """
    Check if a Hazmapper project exists and is accessible
    """
    url = f"https://hazmapper.tacc.utexas.edu/geoapi/projects/?uuid={uuid}"

    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0:
                project_info = data[0]
                return {
                    "currently_working": True,
                    "public": project_info.get("public", False),
                    "hazmapper_project_id": project_info.get("id"),
                    "hazmapper_name": project_info.get("name", ""),
                    "hazmapper_description": project_info.get("description", ""),
                }

        return {
            "currently_working": False,
            "public": False,
            "hazmapper_project_id": None,
            "hazmapper_name": "",
            "hazmapper_description": "",
        }

    except requests.RequestException as e:
        print(f"Error checking Hazmapper project {uuid}: {e}")
        return {
            "currently_working": False,
            "public": False,
            "hazmapper_project_id": None,
            "hazmapper_name": "",
            "hazmapper_description": "",
        }


def extract_hazmapper_maps(project_data: Dict) -> List[Dict]:
    """
    Extract hazmapper map information from project data
    """
    base_project = project_data.get("baseProject", {})
    return base_project.get("hazmapperMaps", [])


def generate_config_file(
    projects_with_maps: List[Dict], output_file: str = "maps_of_published_projects.py"
):
    """
    Generate the Python configuration file
    """
    config_content = '''# noqa: E501
"""
Configuration file for predefined published Hazmapper projects
"""

# Generated automatically from DesignSafe API
predefined_published_maps = [
'''

    for project in projects_with_maps:
        project_id = project["projectId"]
        project_title = project["title"].replace('"', '\\"')  # Escape quotes

        for hazmapper_map in project["hazmapperMaps"]:
            uuid = hazmapper_map.get("uuid")
            if uuid:
                url = f"https://hazmapper.tacc.utexas.edu/hazmapper/project-public/{uuid}/"

                config_content += f"""    {{
        "url": "{url}",
        "designSafeProjectId": "{project_id}",
        "designSafeProjectName": "{project_title}",
        "hazmapper_uuid": "{uuid}",
        "hazmapper_project_id": {hazmapper_map.get('hazmapper_project_id')},
        "currently_working": {hazmapper_map.get('currently_working', False)},
        "public": {hazmapper_map.get('public', False)},
    }},
"""

    config_content += """]
"""

    # Ensure the output directory exists
    output_dir = os.path.dirname(output_file)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(config_content)

    print(f"Configuration file written to: {output_file}")


def generate_readme(
    projects_with_maps: List[Dict], output_file: str = "README_PUBLISHED_MAPS.md"
):
    """
    Generate a README markdown file with project information
    """
    readme_content = """# Published DesignSafe Projects with Hazmapper Maps

This document lists all DesignSafe published projects that have associated Hazmapper maps.

| Project Name | PRJ Number | Hazmapper UUID | Hazmapper ID | Currently Working | Public | Hazmapper Link | DesignSafe Link |
|--------------|------------|----------------|--------------|------------------|--------|----------------|-----------------|
"""  # noqa: E501

    for project in projects_with_maps:
        project_id = project["projectId"]
        project_title = project["title"].replace(
            "|", "\\|"
        )  # Escape pipes for markdown

        for hazmapper_map in project["hazmapperMaps"]:
            uuid = hazmapper_map.get("uuid", "N/A")
            hazmapper_id = hazmapper_map.get("hazmapper_project_id", "N/A")
            currently_working = (
                "✅" if hazmapper_map.get("currently_working", False) else "❌"
            )
            public = "✅" if hazmapper_map.get("public", False) else "❌"

            hazmapper_url = (
                f"https://hazmapper.tacc.utexas.edu/hazmapper/project-public/{uuid}/"
            )
            designsafe_url = f"https://www.designsafe-ci.org/data/browser/public/designsafe.storage.published/{project_id}"  # noqa: E501

            hazmapper_link = f"[View Map]({hazmapper_url})" if uuid != "N/A" else "N/A"
            designsafe_link = f"[View Project]({designsafe_url})"

            readme_content += f"""| {project_title} | {project_id} | {uuid} | {hazmapper_id} | {currently_working} | {public} | {hazmapper_link} | {designsafe_link} |
"""  # noqa: E501

    readme_content += f"""
---
*Generated automatically from DesignSafe and Hazmapper*
*Total projects with Hazmapper maps: {len(projects_with_maps)}*
"""

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(readme_content)

    print(f"README file written to: {output_file}")


def main():
    """
    Main function to orchestrate the discovery process
    """
    parser = argparse.ArgumentParser(
        description="Discover DesignSafe projects with Hazmapper maps"
    )
    parser.add_argument(
        "--short", action="store_true", help="Run short version with only 100 projects"
    )
    parser.add_argument(
        "--python_output_location",
        default=".",
        help="Directory to save the Python config file (default: current directory)",
    )
    args = parser.parse_args()

    print("Starting DesignSafe Hazmapper discovery...")

    # Step 1: Get all projects
    all_projects = get_all_projects(short_version=args.short)

    if not all_projects:
        print("No projects found. Exiting.")
        return

    # Step 2: Check each project for hazmapper maps
    projects_with_maps = []

    print(f"\nChecking {len(all_projects)} projects for Hazmapper maps...")

    for i, project in enumerate(all_projects):
        project_id = project["projectId"]
        print(f"Checking project {i+1}/{len(all_projects)}: {project_id}")

        # Get detailed project information
        project_details = get_project_details(project_id)

        if project_details:
            # Extract hazmapper maps
            hazmapper_maps = extract_hazmapper_maps(project_details)

            if hazmapper_maps:
                print(f"  ✓ Found {len(hazmapper_maps)} Hazmapper map(s)")

                # Check each Hazmapper map
                enhanced_maps = []
                for hm_map in hazmapper_maps:
                    uuid = hm_map.get("uuid")
                    if uuid:
                        print(f"    Checking Hazmapper status for UUID: {uuid}")
                        hazmapper_status = check_hazmapper_project(uuid)

                        # Merge the original map data with status
                        enhanced_map = {**hm_map, **hazmapper_status}
                        enhanced_maps.append(enhanced_map)

                        status_msg = (
                            "✅ Working"
                            if hazmapper_status["currently_working"]
                            else "❌ Not accessible"
                        )
                        public_msg = (
                            "Public" if hazmapper_status["public"] else "Private"
                        )
                        print(
                            f"      {status_msg}, {public_msg},"
                            f" ID: {hazmapper_status.get('hazmapper_project_id', 'N/A')}"
                        )
                    else:
                        enhanced_maps.append(hm_map)

                projects_with_maps.append(
                    {
                        "projectId": project_id,
                        "title": project["title"],
                        "hazmapperMaps": enhanced_maps,
                    }
                )
            else:
                print("  - No Hazmapper maps found")

        # Be respectful with API calls
        time.sleep(SLEEP_TIME)

    # Sort projects by PRJ number
    projects_with_maps.sort(key=lambda x: x["projectId"])

    print(f"\nFound {len(projects_with_maps)} projects with Hazmapper maps:")
    for project in projects_with_maps:
        print(f"  - {project['projectId']}: {project['title']}")
        for hm_map in project["hazmapperMaps"]:
            status = (
                "Working" if hm_map.get("currently_working", False) else "Not working"
            )
            public = "Public" if hm_map.get("public", False) else "Private"
            print(
                f"    UUID: {hm_map.get('uuid', 'N/A')}, ID: {hm_map.get('hazmapper_project_id', 'N/A')}, Status: {status}, {public}"  # noqa: E501
            )

    # Step 3: Generate configuration file and README
    if projects_with_maps:
        # Create Python config file path
        python_output_path = os.path.join(
            args.python_output_location, "maps_of_published_projects.py"
        )
        generate_config_file(projects_with_maps, python_output_path)
        generate_readme(projects_with_maps)
        print(f"\nGenerated configuration file with {len(projects_with_maps)} projects")
    else:
        print("\nNo projects with Hazmapper maps found.")

    # Save raw data as JSON for reference
    with open("projects_with_hazmapper_maps.json", "w", encoding="utf-8") as f:
        json.dump(projects_with_maps, f, indent=2)
    print("Raw data saved to: projects_with_hazmapper_maps.json")


if __name__ == "__main__":
    main()
