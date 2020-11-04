import requests
import supervisely_lib as sly

url = "https://file-examples-com.github.io/uploads/2017/04/file_example_MP4_480_1_5MG.mp4"

local_path = "/sly_task_data/{}".format(sly.fs.get_file_name_with_ext(url))
print(local_path)

def download_file(url, local_path):
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        with open(local_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return local_path

download_file(url, local_path)
print("downloaded")
#exit(0)

api = sly.Api.from_env()

team_id = 7
workspace_id = 12

project_name = "my videos"
dataset_name = "dataset_xxx"

project = api.project.get_info_by_name(workspace_id, project_name)
if project is None:
    project = api.project.create(workspace_id, "my videos", type=sly.ProjectType.VIDEOS)

dataset = api.dataset.get_info_by_name(project.id, dataset_name)
if dataset is None:
    dataset = api.dataset.create(project.id, "dataset_xxx")

video_info = api.video.upload_paths(dataset.id,
                                    names=[sly.fs.get_file_name_with_ext(local_path)],
                                    paths=[local_path])

print("uploaded")
print(video_info[0])