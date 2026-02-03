import subprocess
import os
from collections import defaultdict

# Get the absolute path of the script's directory, then go up to the project root.
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Define files to track per language. Paths are relative to the project root.
files_by_lang = {
    "c": ["src/codegraphcontext/tools/languages/c.py"],
    "cpp": ["src/codegraphcontext/tools/languages/cpp.py"],
    "go": ["src/codegraphcontext/tools/languages/go.py"],
    "java": ["src/codegraphcontext/tools/languages/java.py"],
    "javascript": ["src/codegraphcontext/tools/languages/javascript.py"],
    "python": ["src/codegraphcontext/tools/languages/python.py"],
    "ruby": ["src/codegraphcontext/tools/languages/ruby.py"],
    "rust": ["src/codegraphcontext/tools/languages/rust.py"],
    "typescript": ["src/codegraphcontext/tools/languages/typescript.py"],
}

def get_contributor_stats(files):
    """
    Returns a dictionary of contributors with commit count, lines added, and lines deleted.
    This is done by parsing the output of 'git log'.
    """
    data = defaultdict(lambda: {"commits": 0, "added": 0, "deleted": 0, "email": ""})
    
    try:
        # Use 'git log' with '--numstat' to get file changes, author name, and email in one go.
        log_output = subprocess.check_output(
            ["git", "log", "--no-merges", "--numstat", "--pretty=format:---%n%an%n%ae", "--"] + files,
            text=True,
            cwd=PROJECT_ROOT
        ).strip()
    except subprocess.CalledProcessError as e:
        print(f"Error fetching git log for files {files}: {e}")
        return data

    if not log_output:
        return data

    commits = log_output.split('---')[1:]

    for commit in commits:
        lines = commit.strip().split('\n')
        author = lines[0].strip()
        email = lines[1].strip()
        if not author:
            continue
        
        data[author]["commits"] += 1
        data[author]["email"] = email
        
        for line in lines[2:]:
            if not line.strip():
                continue
            
            parts = line.split("\t")
            if len(parts) >= 3:
                added, deleted, _ = parts
                added = int(added) if added != "-" else 0
                deleted = int(deleted) if deleted != "-" else 0
                data[author]["added"] += added
                data[author]["deleted"] += deleted
                
    return data

def get_username_from_email(email):
    if email.endswith('@users.noreply.github.com'):
        return email.split('+')[1].split('@')[0]
    return None

def get_repo_url():
    try:
        url = subprocess.check_output(
            ["git", "remote", "get-url", "origin"],
            text=True,
            cwd=PROJECT_ROOT
        ).strip()
        if url.endswith(".git"):
            url = url[:-4]
        if url.startswith("git@github.com:"):
            url = url.replace("git@github.com:", "https://github.com/")
        return url
    except Exception:
        return None

def generate_markdown_table(lang, stats, repo_url, files):
    """
    Generates a Markdown table for contributors
    """
    table = f"## {lang.capitalize()} Contributors\n\n"
    table += "| Rank | Contributor | Commits | Lines Added | Lines Deleted | Link to Contributions |\n"
    table += "|---|---|---|---|---|---|\n"

    for rank, (author, vals) in enumerate(sorted(stats.items(), key=lambda x: (x[1]["commits"], x[1]["added"]), reverse=True), 1):
        email = vals["email"]
        username = get_username_from_email(email)
        
        if username:
            profile_str = f"[{author}](https://github.com/{username})"
            author_for_link = username
        else:
            profile_str = author
            author_for_link = email

        contribution_links = []
        for path in files:
            file_name = os.path.basename(path)
            link = f"[{file_name}]({repo_url}/commits/main/{path}?author={author_for_link})"
            contribution_links.append(link)
        
        links_str = ", ".join(contribution_links)

        table += f"| {rank} | {profile_str} | {vals['commits']} | {vals['added']} | {vals['deleted']} | {links_str} |\n"
    
    return table

def main():
    repo_url = get_repo_url()
    if not repo_url:
        print("Could not determine repository URL. Contribution links will not be generated.")

    output_file = os.path.join(PROJECT_ROOT, "contributors.md")
    with open(output_file, "w") as f:
        f.write("# Language Contributors\n\n")
        f.write("This file is auto-generated. Do not edit manually.\n\n")
        for lang, files in files_by_lang.items():
            stats = get_contributor_stats(files)
            if stats:
                table = generate_markdown_table(lang, stats, repo_url, files)
                f.write(table + "\n\n")
    print(f"Contributor stats generated in {output_file}")

if __name__ == "__main__":
    main()
