import os
import supervisely_lib as sly
from supervisely_lib.video_annotation.video_tag import VideoTag

api = sly.Api(server_address=os.environ['SERVER_ADDRESS'], token=os.environ['API_TOKEN'])
#or
#api = sly.Api.from_env()


project_id = 1432
project = api.project.get_info_by_id(project_id)
if project is None:
    raise RuntimeError(f"Project id={project.id} not found")
if project.type != str(sly.ProjectType.VIDEOS):
    raise TypeError("Not a video project")

meta_json = api.project.get_meta(project.id)
meta = sly.ProjectMeta.from_json(meta_json)
print(meta)

tag = meta.get_tag_meta('vehicle_colour')
print(tag.sly_id)

dataset = api.dataset.create(project.id, "test_dataset", change_name_if_conflict=True)

local_path = "/my_data/car.mp4"

# metadata is optional
video_metadata = {
    "field1": "value1",
    "field2": "value2"
}

#smart upload - if video already uploaded to server, it will be added by hash to dataset withoud direct upload
video_infos = api.video.upload_paths(dataset.id, ["car.mp4"], [local_path], metas=[video_metadata])
video_info = video_infos[0]

print(video_info)
print("uploaded video id: ", video_info.id)

tags_to_assign = [
    VideoTag(tag, value="red", frame_range=[3, 17]),
    VideoTag(tag, value="orange", frame_range=[22, 30]),
]
api.video.tag.append_to_entity(video_info.id, project.id, tags=sly.TagCollection(tags_to_assign))

# see screenshot with result
# https://i.imgur.com/eVtfY1k.png