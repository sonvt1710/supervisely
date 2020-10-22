import supervisely_lib as sly

api = sly.Api.from_env()

info = api.labeling_job.get_info_by_id(id=2153)

# prints list of images (id, name, review status)
print(info.entities)