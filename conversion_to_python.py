import textwrap

full_conversion_path = "/mnt/data/true_contributors_mixin_full.py"

# Full class implementation with mocks for GitHub API interactions
class_code = textwrap.dedent('''\
    # true_contributors_mixin_full.py

    from typing import List, Dict, Callable, Any
    from collections import defaultdict

    class GitHubAPIStub:
        """Stub class to simulate GitHub API structure used in the mixin."""
        def __init__(self):
            self.repos = self.RepoStub()
            self.issues = self.IssueStub()

        class RepoStub:
            def listCommits(self, params):
                return [{"author": {"id": 1, "login": "alice"}},
                        {"author": {"id": 2, "login": "bob"}}]

            def listContributors(self, params):
                return {"status": 204, "headers": {"status": "204 No Content"}}

            def listForOrg(self, params):
                return [
                    {"owner": {"login": "org"}, "name": "repo1"},
                    {"owner": {"login": "org"}, "name": "repo2"}
                ]

        class IssueStub:
            def listCommentsForRepo(self, params):
                return [{"user": {"id": 1, "login": "alice"}},
                        {"user": {"id": 3, "login": "charlie"}}]

        def paginate(self, func, params):
            # Simulated pagination logic (returns direct result)
            return func(params)

    class TrueContributorsMixin:
        def __init__(self):
            self.api = GitHubAPIStub()
            self.repos = self.api.repos
            self.issues = self.api.issues
            self.paginate = self.api.paginate

        def listCommitCommentContributorsForOrg(self, parameters):
            return self._listForOrgHelper(self.listCommitCommentContributors, parameters)

        def listCommitContributorsForOrg(self, parameters):
            return self._listForOrgHelper(self.listCommitContributors, parameters)

        def listContributorsForOrg(self, parameters):
            return self._listForOrgHelper(self._listContributors, parameters)

        def listCommentContributorsForOrg(self, parameters):
            return self._listForOrgHelper(self.listCommentContributors, parameters)

        def listCommitCommentContributors(self, parameters):
            params = self._createParamsFromObject(["owner", "repo", "since"], parameters)
            contributors = (
                self.listCommitContributors(params)
                if "since" in params
                else self._listContributors(params)
            )
            comments = self.listCommentContributors(params)
            return self._aggregateContributors(contributors + comments)

        def listCommitContributors(self, parameters):
            params = self._createParamsFromObject(
                ["owner", "repo", "sha", "path", "since", "until"], parameters
            )
            try:
                commits = self.paginate(self.repos.listCommits, params)
            except Exception as err:
                if getattr(err, 'status', None) != 409 or str(err) != "Git Repository is empty.":
                    raise
                commits = []
            return self._aggregateContributions(commits, "author")

        def listCommentContributors(self, parameters):
            params = self._createParamsFromObject(["owner", "repo", "since"], parameters)
            comments = self.paginate(self.issues.listCommentsForRepo, params)
            return self._aggregateContributions(comments, "user")

        def _listForOrgHelper(self, endpoint: Callable, parameters: Dict):
            valid_endpoints = [
                self.listCommentContributors,
                self._listContributors,
                self.listCommitContributors,
                self.listCommitCommentContributors,
            ]
            if endpoint not in valid_endpoints:
                raise TypeError("Unexpected endpoint function provided.")
            org_params = self._createParamsFromObject(["org", "type"], parameters)
            repos = self.paginate(self.repos.listForOrg, org_params)

            contributors = []
            for repo in repos:
                params = {"owner": repo["owner"]["login"], "repo": repo["name"], **parameters}
                contributors += endpoint(params)
            return self._aggregateContributors(contributors)

        def _listContributors(self, parameters):
            try:
                return self.paginate(self.repos.listContributors, parameters)
            except Exception:
                res = self.repos.listContributors(parameters)
                if res.get("status") != 204 or res.get("headers", {}).get("status") != "204 No Content":
                    raise
                return []

        def _aggregateContributions(self, items, key):
            if not key:
                raise ReferenceError("Missing key for contribution.")
            contributors = [
                {**item[key], "contributions": 1}
                for item in items if key in item and item[key]
            ]
            return self._aggregateContributors(contributors)

        def _aggregateContributors(self, contributors: List[Dict]):
            counts = defaultdict(lambda: {"contributions": 0})
            for contributor in contributors:
                uid = contributor["id"]
                if "login" in contributor:
                    counts[uid]["login"] = contributor["login"]
                counts[uid]["id"] = uid
                counts[uid]["contributions"] += contributor["contributions"]
            return sorted(counts.values(), key=lambda c: c["contributions"], reverse=True)

        def _createParamsFromObject(self, keys: List[str], params: Dict) -> Dict:
            return {k: params[k] for k in keys if k in params}
''')

# Write the full Python conversion to disk
with open(full_conversion_path, "w") as f:
    f.write(class_code)

full_conversion_path
