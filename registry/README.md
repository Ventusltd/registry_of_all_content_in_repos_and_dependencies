# Registry operating rules

This folder is the authoritative kernel index for the GlobalGrid2050 federation.

The version named in `latest.json` is authoritative.

Every earlier numbered JSON file is a frozen restore point.

Nothing ever overwrites an existing numbered registry file. New runs write the next file in the sequence, for example `registry_v0001.json`, `registry_v0002.json`, `registry_v0003.json`.

`registry.md` is generated from the current authoritative JSON and must not be edited by hand.

If an accidental overwrite, truncation, or collapse toward zero is detected, the fix is to repoint `latest.json` back to the last good numbered version, then re-run the builder.

The registry is audit-first:

- never invent file contents
- never silently overwrite previous versions
- detect every repo default branch rather than assuming `main`
- use the GitHub REST API git trees endpoint for recursive file enumeration
- mark unknown or unreadable states honestly
- keep restore points intact

Data source for the registry:

```text
GitHub REST API
GET /repos/{owner}/{repo}
GET /repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1
```

Repos in scope:

```text
Ventusltd/data_uk_dno_and_tso
Ventusltd/data-federation-map-for-globalgrid2050-all-repos
Ventusltd/globalgrid2050
Ventusltd/spiders
Ventusltd/data-gb-electricity
Ventusltd/registry_of_all_content_in_repos_and_dependencies
```
