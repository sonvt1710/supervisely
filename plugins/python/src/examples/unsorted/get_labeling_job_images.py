import supervisely_lib as sly

api = sly.Api.from_env()

info = api.labeling_job.get_info_by_id(id=9704)
# prints list of images (id, name, review status)
print(info.entities)

jobs = api.labeling_job.get_list(team_id=600)
print(len(jobs))