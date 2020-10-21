# coding: utf-8
import os
from collections import defaultdict
from supervisely_lib.io.json import load_json_file
from supervisely_lib import TaskPaths
import supervisely_lib as sly
from supervisely_lib.video.import_utils import get_dataset_name


DEFAULT_DATASET_NAME = 'ds0'
root_ds_name = DEFAULT_DATASET_NAME


def add_images_to_project():
    sly.fs.ensure_base_path(sly.TaskPaths.RESULTS_DIR)

    task_config = load_json_file(TaskPaths.TASK_CONFIG_PATH)

    task_id = task_config['task_id']
    append_to_existing_project = task_config['append_to_existing_project']
    server_address = task_config['server_address']
    token = task_config['api_token']

    convert_options = task_config.get('options', {})
    normalize_exif = convert_options.get('normalize_exif', True)
    remove_alpha_channel = convert_options.get('remove_alpha_channel', True)
    need_download = normalize_exif or remove_alpha_channel

    api = sly.Api(server_address, token, retry_count=5)

    task_info = api.task.get_info_by_id(task_id)
    api.add_additional_field('taskId', task_id)
    api.add_header('x-task-id', str(task_id))

    workspace_id = task_info["workspaceId"]
    project_name = task_config.get('project_name', None)
    if project_name is None:
        project_name = task_config["res_names"]["project"]

    project_info = None
    if append_to_existing_project is True:
        project_info = api.project.get_info_by_name(workspace_id, project_name, expected_type=sly.ProjectType.IMAGES, raise_error=True)
    else:
        project_info = api.project.create(workspace_id, project_name, type=sly.ProjectType.IMAGES, change_name_if_conflict=True)

    files_list = api.task.get_import_files_list(task_id)
    dataset_to_item = defaultdict(dict)
    for file_info in files_list:
        original_path = file_info["filename"]
        try:
            sly.image.validate_ext(original_path)
            item_hash = file_info["hash"]
            ds_name = get_dataset_name(original_path)
            item_name = sly.fs.get_file_name_with_ext(original_path)
            if item_name in dataset_to_item[ds_name]:
                temp_name = sly.fs.get_file_name(original_path)
                temp_ext = sly.fs.get_file_ext(original_path)
                new_item_name = "{}_{}{}".format(temp_name, sly.rand_str(5), temp_ext)
                sly.logger.warning("Name {!r} already exists in dataset {!r}: renamed to {!r}"
                                   .format(item_name, ds_name, new_item_name))
                item_name = new_item_name
            dataset_to_item[ds_name][item_name] = item_hash
        except Exception as e:
            sly.logger.warning("File skipped {!r}: error occurred during processing {!r}".format(original_path, str(e)))

    for ds_name, ds_items in dataset_to_item.items():
        ds_info = api.dataset.get_or_create(project_info.id, ds_name)

        names = list(ds_items.keys())
        hashes = list(ds_items.values())
        paths = [os.path.join(sly.TaskPaths.RESULTS_DIR, h.replace("/", "a") + sly.image.DEFAULT_IMG_EXT) for h in hashes]
        progress = sly.Progress('Dataset: {!r}'.format(ds_name), len(ds_items))

        for batch_names, batch_hashes, batch_paths in zip(sly.batched(names, 10), sly.batched(hashes, 10), sly.batched(paths, 10)):
            if need_download is True:
                api.image.download_paths_by_hashes(batch_hashes, batch_paths)
                for path in batch_paths:
                    img = sly.image.read(path, remove_alpha_channel)
                    sly.image.write(path, img, remove_alpha_channel)
                api.image.upload_paths(ds_info.id, batch_names, batch_paths)
                sly.fs.clean_dir(sly.TaskPaths.RESULTS_DIR)
            else:
                api.image.upload_hashes(ds_info.id, batch_names, batch_hashes, progress_cb=progress.iters_done_report)
            progress.iters_done_report(len(batch_names))

    if project_info is not None:
        sly.logger.info('PROJECT_CREATED', extra={'event_type': sly.EventType.PROJECT_CREATED, 'project_id': project_info.id})
    else:
        temp_str = "Project"
        if append_to_existing_project is True:
            temp_str = "Dataset"
        raise RuntimeError("{} wasn't created: 0 files were added")
    pass


def main():
    add_images_to_project()
    sly.report_import_finished()


if __name__ == '__main__':
    sly.main_wrapper('IMPORT_IMAGES', main)
