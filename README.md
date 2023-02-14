# What is this
This is an example of simple Nwave GraphQL API client. It enables to get the occupancy data on demand or subscribe to occupancy data change notifications.

# Preparation
1. Install Python 3 and Pip
2. Install `poetry`
```shell
$ pip install poetry 
```
3. Install dependencies
```shell
$ poetry install
```
# Example running
1. Open file `tests/example.py` in an editor
2. Replace value of variable `AUTH_TOKEN` by your Nwave authorization token
3. Replace values of variable `ZONE_ID` and `FLOOR_NUMBER` by identifiers of your infrastructure objects
4. Run the example by command 
```shell
$ PYTHONPATH=src poetry run python3 ./tests/example.py
```