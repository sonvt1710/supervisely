# coding: utf-8
"""api for working with tasks"""

import json
import os
import time
from collections import OrderedDict, defaultdict
from pathlib import Path

# docs
from typing import Any, Callable, Dict, List, Literal, NamedTuple, Optional, Union

from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor
from tqdm import tqdm

from supervisely import logger
from supervisely._utils import batched, take_with_default
from supervisely.api.module_api import (
    ApiField,
    ModuleApiBase,
    ModuleWithStatus,
    WaitingTimeExceeded,
)
from supervisely.collection.str_enum import StrEnum
from supervisely.io.fs import (
    ensure_base_path,
    get_file_hash,
    get_file_name,
    get_file_name_with_ext,
)


class TaskFinishedWithError(Exception):
    """TaskFinishedWithError"""

    pass


class TaskApi(ModuleApiBase, ModuleWithStatus):
    """
    API for working with Tasks. :class:`TaskApi<TaskApi>` object is immutable.

    :param api: API connection to the server.
    :type api: Api
    :Usage example:

     .. code-block:: python

        import os
        from dotenv import load_dotenv

        import supervisely as sly

        # Load secrets and create API object from .env file (recommended)
        # Learn more here: https://developer.supervisely.com/getting-started/basics-of-authentication
        if sly.is_development():
            load_dotenv(os.path.expanduser("~/supervisely.env"))
        api = sly.Api.from_env()

        # Pass values into the API constructor (optional, not recommended)
        # api = sly.Api(server_address="https://app.supervise.ly", token="4r47N...xaTatb")

        task_id = 121230
        task_info = api.task.get_info_by_id(task_id)
    """

    class RestartPolicy(StrEnum):
        """RestartPolicy"""

        NEVER = "never"
        """"""
        ON_ERROR = "on_error"
        """"""

    class PluginTaskType(StrEnum):
        """PluginTaskType"""

        TRAIN = "train"
        """"""
        INFERENCE = "inference"
        """"""
        INFERENCE_RPC = "inference_rpc"
        """"""
        SMART_TOOL = "smarttool"
        """"""
        CUSTOM = "custom"
        """"""

    class Status(StrEnum):
        """Status"""

        QUEUED = "queued"
        """Application is queued for execution"""
        CONSUMED = "consumed"
        """Application is consumed by an agent"""
        STARTED = "started"
        """Application has been started"""
        DEPLOYED = "deployed"
        """Only for Plugins"""
        ERROR = "error"
        """Application has finished with an error"""
        FINISHED = "finished"
        """Application has finished successfully"""
        TERMINATING = "terminating"
        """Application is being terminated"""
        STOPPED = "stopped"
        """Application has been stopped"""

    def __init__(self, api):
        ModuleApiBase.__init__(self, api)
        ModuleWithStatus.__init__(self)

    def get_list(
        self, workspace_id: int, filters: Optional[List[Dict[str, str]]] = None
    ) -> List[NamedTuple]:
        """
        List of Tasks in the given Workspace.

        :param workspace_id: Workspace ID.
        :type workspace_id: int
        :param filters: List of params to sort output Projects.
        :type filters: List[dict], optional
        :return: List of Tasks with information for the given Workspace.
        :rtype: :class:`List[NamedTuple]`
        :Usage example:

         .. code-block:: python

            import supervisely as sly

            workspace_id = 23821

            os.environ['SERVER_ADDRESS'] = 'https://app.supervisely.com'
            os.environ['API_TOKEN'] = 'Your Supervisely API Token'
            api = sly.Api.from_env()

            task_infos = api.task.get_list(workspace_id)

            task_infos_filter = api.task.get_list(23821, filters=[{'field': 'id', 'operator': '=', 'value': 121230}])
            print(task_infos_filter)
            # Output: [
            #     {
            #         "id": 121230,
            #         "type": "clone",
            #         "status": "finished",
            #         "startedAt": "2019-12-19T12:13:09.702Z",
            #         "finishedAt": "2019-12-19T12:13:09.701Z",
            #         "meta": {
            #             "input": {
            #                 "model": {
            #                     "id": 1849
            #                 },
            #                 "isExternal": true,
            #                 "pluginVersionId": 84479
            #             },
            #             "output": {
            #                 "model": {
            #                     "id": 12380
            #                 },
            #                 "pluginVersionId": 84479
            #             }
            #         },
            #         "description": ""
            #     }
            # ]
        """
        return self.get_list_all_pages(
            "tasks.list",
            {ApiField.WORKSPACE_ID: workspace_id, ApiField.FILTER: filters or []},
        )

    def get_info_by_id(self, id: int) -> NamedTuple:
        """
        Get Task information by ID.

        :param id: Task ID in Supervisely.
        :type id: int
        :return: Information about Task.
        :rtype: :class:`NamedTuple`
        :Usage example:

         .. code-block:: python

            import supervisely as sly

            task_id = 121230

            os.environ['SERVER_ADDRESS'] = 'https://app.supervisely.com'
            os.environ['API_TOKEN'] = 'Your Supervisely API Token'
            api = sly.Api.from_env()

            task_info = api.task.get_info_by_id(task_id)
            print(task_info)
            # Output: {
            #     "id": 121230,
            #     "workspaceId": 23821,
            #     "description": "",
            #     "type": "clone",
            #     "status": "finished",
            #     "startedAt": "2019-12-19T12:13:09.702Z",
            #     "finishedAt": "2019-12-19T12:13:09.701Z",
            #     "userId": 16154,
            #     "meta": {
            #         "app": {
            #             "id": 10370,
            #             "name": "Auto Import",
            #             "version": "test-branch",
            #             "isBranch": true,
            #         },
            #         "input": {
            #             "model": {
            #                 "id": 1849
            #             },
            #             "isExternal": true,
            #             "pluginVersionId": 84479
            #         },
            #         "output": {
            #             "model": {
            #                 "id": 12380
            #             },
            #             "pluginVersionId": 84479
            #         }
            #     },
            #     "settings": {},
            #     "agentName": null,
            #     "userLogin": "alexxx",
            #     "teamId": 16087,
            #     "agentId": null
            # }
        """
        return self._get_info_by_id(id, "tasks.info")

    def get_status(self, task_id: int) -> Status:
        """
        Check status of Task by ID.

        :param id: Task ID in Supervisely.
        :type id: int
        :return: Status object
        :rtype: :class:`Status`
        :Usage example:

         .. code-block:: python

            import supervisely as sly

            task_id = 121230

            os.environ['SERVER_ADDRESS'] = 'https://app.supervisely.com'
            os.environ['API_TOKEN'] = 'Your Supervisely API Token'
            api = sly.Api.from_env()

            task_status = api.task.get_status(task_id)
            print(task_status)
            # Output: finished
        """
        status_str = self.get_info_by_id(task_id)[ApiField.STATUS]  # @TODO: convert json to tuple
        return self.Status(status_str)

    def raise_for_status(self, status: Status) -> None:
        """
        Raise error if Task status is ERROR.

        :param status: Status object.
        :type status: Status
        :return: None
        :rtype: :class:`NoneType`
        """
        if status is self.Status.ERROR:
            raise TaskFinishedWithError(f"Task finished with status {str(self.Status.ERROR)}")

    def wait(
        self,
        id: int,
        target_status: Status,
        wait_attempts: Optional[int] = None,
        wait_attempt_timeout_sec: Optional[int] = None,
    ):
        """
        Awaiting achievement by given Task of a given status.

        :param id: Task ID in Supervisely.
        :type id: int
        :param target_status: Status object(status of task we expect to destinate).
        :type target_status: Status
        :param wait_attempts: The number of attempts to determine the status of the task that we are waiting for.
        :type wait_attempts: int, optional
        :param wait_attempt_timeout_sec: Number of seconds for intervals between attempts(raise error if waiting time exceeded).
        :type wait_attempt_timeout_sec: int, optional
        :return: True if the desired status is reached, False otherwise
        :rtype: :class:`bool`
        """
        wait_attempts = wait_attempts or self.MAX_WAIT_ATTEMPTS
        effective_wait_timeout = wait_attempt_timeout_sec or self.WAIT_ATTEMPT_TIMEOUT_SEC
        for attempt in range(wait_attempts):
            status = self.get_status(id)
            self.raise_for_status(status)
            if status in [
                target_status,
                self.Status.FINISHED,
                self.Status.DEPLOYED,
                self.Status.STOPPED,
            ]:
                return
            time.sleep(effective_wait_timeout)
        raise WaitingTimeExceeded(
            f"Waiting time exceeded: total waiting time {wait_attempts * effective_wait_timeout} seconds, i.e. {wait_attempts} attempts for {effective_wait_timeout} seconds each"
        )

    def upload_dtl_archive(
        self,
        task_id: int,
        archive_path: str,
        progress_cb: Optional[Union[tqdm, Callable]] = None,
    ):
        """upload_dtl_archive"""
        encoder = MultipartEncoder(
            {
                "id": str(task_id).encode("utf-8"),
                "name": get_file_name(archive_path),
                "archive": (
                    os.path.basename(archive_path),
                    open(archive_path, "rb"),
                    "application/x-tar",
                ),
            }
        )

        def callback(monitor_instance):
            read_mb = monitor_instance.bytes_read / 1024.0 / 1024.0
            if progress_cb is not None:
                progress_cb(read_mb)

        monitor = MultipartEncoderMonitor(encoder, callback)
        self._api.post("tasks.upload.dtl_archive", monitor)

    def _deploy_model(
        self,
        agent_id,
        model_id,
        plugin_id=None,
        version=None,
        restart_policy=RestartPolicy.NEVER,
        settings=None,
    ):
        """_deploy_model"""
        response = self._api.post(
            "tasks.run.deploy",
            {
                ApiField.AGENT_ID: agent_id,
                ApiField.MODEL_ID: model_id,
                ApiField.RESTART_POLICY: restart_policy.value,
                ApiField.SETTINGS: settings or {"gpu_device": 0},
                ApiField.PLUGIN_ID: plugin_id,
                ApiField.VERSION: version,
            },
        )
        return response.json()[ApiField.TASK_ID]

    def get_context(self, id: int) -> Dict:
        """
        Get context information by task ID.

        :param id: Task ID in Supervisely.
        :type id: int
        :return: Context information in dict format
        :rtype: :class:`dict`
        :Usage example:

         .. code-block:: python

            import supervisely as sly

            task_id = 121230

            os.environ['SERVER_ADDRESS'] = 'https://app.supervisely.com'
            os.environ['API_TOKEN'] = 'Your Supervisely API Token'
            api = sly.Api.from_env()

            context = api.task.get_context(task_id)
            print(context)
            # Output: {
            #     "team": {
            #         "id": 16087,
            #         "name": "alexxx"
            #     },
            #     "workspace": {
            #         "id": 23821,
            #         "name": "my_super_workspace"
            #     }
            # }
        """
        response = self._api.post("GetTaskContext", {ApiField.ID: id})
        return response.json()

    def _convert_json_info(self, info: dict):
        """_convert_json_info"""
        return info

    def run_dtl(self, workspace_id: int, dtl_graph: Dict, agent_id: Optional[int] = None):
        """run_dtl"""
        response = self._api.post(
            "tasks.run.dtl",
            {
                ApiField.WORKSPACE_ID: workspace_id,
                ApiField.CONFIG: dtl_graph,
                "advanced": {ApiField.AGENT_ID: agent_id},
            },
        )
        return response.json()[ApiField.TASK_ID]

    def _run_plugin_task(
        self,
        task_type,
        agent_id,
        plugin_id,
        version,
        config,
        input_projects,
        input_models,
        result_name,
    ):
        """_run_plugin_task"""
        response = self._api.post(
            "tasks.run.plugin",
            {
                "taskType": task_type,
                ApiField.AGENT_ID: agent_id,
                ApiField.PLUGIN_ID: plugin_id,
                ApiField.VERSION: version,
                ApiField.CONFIG: config,
                "projects": input_projects,
                "models": input_models,
                ApiField.NAME: result_name,
            },
        )
        return response.json()[ApiField.TASK_ID]

    def run_train(
        self,
        agent_id: int,
        input_project_id: int,
        input_model_id: int,
        result_nn_name: str,
        train_config: Optional[Dict] = None,
    ):
        """run_train"""
        model_info = self._api.model.get_info_by_id(input_model_id)
        return self._run_plugin_task(
            task_type=TaskApi.PluginTaskType.TRAIN.value,
            agent_id=agent_id,
            plugin_id=model_info.plugin_id,
            version=None,
            input_projects=[input_project_id],
            input_models=[input_model_id],
            result_name=result_nn_name,
            config={} if train_config is None else train_config,
        )

    def run_inference(
        self,
        agent_id: int,
        input_project_id: int,
        input_model_id: int,
        result_project_name: str,
        inference_config: Optional[Dict] = None,
    ):
        """run_inference"""
        model_info = self._api.model.get_info_by_id(input_model_id)
        return self._run_plugin_task(
            task_type=TaskApi.PluginTaskType.INFERENCE.value,
            agent_id=agent_id,
            plugin_id=model_info.plugin_id,
            version=None,
            input_projects=[input_project_id],
            input_models=[input_model_id],
            result_name=result_project_name,
            config={} if inference_config is None else inference_config,
        )

    def get_training_metrics(self, task_id: int):
        """get_training_metrics"""
        response = self._get_response_by_id(
            id=task_id, method="tasks.train-metrics", id_field=ApiField.TASK_ID
        )
        return response.json() if (response is not None) else None

    def deploy_model(self, agent_id: int, model_id: int) -> int:
        """deploy_model"""
        task_ids = self._api.model.get_deploy_tasks(model_id)
        if len(task_ids) == 0:
            task_id = self._deploy_model(agent_id, model_id)
        else:
            task_id = task_ids[0]
        self.wait(task_id, self.Status.DEPLOYED)
        return task_id

    def deploy_model_async(self, agent_id: int, model_id: int) -> int:
        """deploy_model_async"""
        task_ids = self._api.model.get_deploy_tasks(model_id)
        if len(task_ids) == 0:
            task_id = self._deploy_model(agent_id, model_id)
        else:
            task_id = task_ids[0]
        return task_id

    def start(
        self,
        agent_id,
        app_id: Optional[int] = None,
        workspace_id: Optional[int] = None,
        description: Optional[str] = "application description",
        params: Dict[str, Any] = None,
        log_level: Optional[Literal["info", "debug", "warning", "error"]] = "info",
        users_ids: Optional[List[int]] = None,
        app_version: Optional[str] = "",
        is_branch: Optional[bool] = False,
        task_name: Optional[str] = "pythonSpawned",
        restart_policy: Optional[Literal["never", "on_error"]] = "never",
        proxy_keep_url: Optional[bool] = False,
        module_id: Optional[int] = None,
        redirect_requests: Optional[Dict[str, int]] = {},
        limit_by_workspace: bool = False,
    ) -> Dict[str, Any]:
        """Starts the application task on the agent.

        :param agent_id: Agent ID. Can be obtained from TeamCluster page in UI.
        :type agent_id: int
        :param app_id: Deprecated. Use module_id instead.
        :type app_id: int, optional
        :param workspace_id: Workspace ID where the task will be created.
        :type workspace_id: int, optional
        :param description: Task description which will be shown in UI.
        :type description: str, optional
        :param params: Task parameters which will be passed to the application, check the
            code example below for more details.
        :type params: Dict[str, Any], optional
        :param log_level: Log level for the application.
        :type log_level: Literal["info", "debug", "warning", "error"], optional
        :param users_ids: List of user IDs for which will be created an instance of the application.
            For each user a separate task will be created.
        :type users_ids: List[int], optional
        :param app_version: Application version e.g. "v1.0.0" or branch name e.g. "dev".
        :type app_version: str, optional
        :param is_branch: If the application version is a branch name, set this parameter to True.
        :type is_branch: bool, optional
        :param task_name: Task name which will be shown in UI.
        :type task_name: str, optional
        :param restart_policy: when the task should be restarted: never or if error occurred.
        :type restart_policy: Literal["never", "on_error"], optional
        :param proxy_keep_url: For internal usage only.
        :type proxy_keep_url: bool, optional
        :param module_id: Module ID. Can be obtained from the apps page in UI.
        :type module_id: int, optional
        :param redirect_requests: For internal usage only in Develop and Debug mode.
        :type redirect_requests: Dict[str, int], optional
        :param limit_by_workspace: If set to True tasks will be only visible inside of the workspace
            with specified workspace_id.
        :type limit_by_workspace: bool, optional
        :return: Task information in JSON format.
        :rtype: Dict[str, Any]

        :Usage example:

         .. code-block:: python

            import supervisely as sly

            app_slug = "supervisely-ecosystem/export-to-supervisely-format"
            module_id = api.app.get_ecosystem_module_id(app_slug)
            module_info = api.app.get_ecosystem_module_info(module_id)

            project_id = 12345
            agent_id = 12345
            workspace_id = 12345

            params = module_info.get_arguments(images_project=project_id)

            session = api.app.start(
                agent_id=agent_id,
                module_id=module_id,
                workspace_id=workspace_id,
                task_name="Prepare download link",
                params=params,
                app_version="dninja",
                is_branch=True,
            )
        """
        if app_id is not None and module_id is not None:
            raise ValueError("Only one of the arguments (app_id or module_id) have to be defined")
        if app_id is None and module_id is None:
            raise ValueError("One of the arguments (app_id or module_id) have to be defined")

        advanced_settings = {
            ApiField.LIMIT_BY_WORKSPACE: limit_by_workspace,
        }

        data = {
            ApiField.AGENT_ID: agent_id,
            # "nodeId": agent_id,
            ApiField.WORKSPACE_ID: workspace_id,
            ApiField.DESCRIPTION: description,
            ApiField.PARAMS: take_with_default(params, {"state": {}}),
            ApiField.LOG_LEVEL: log_level,
            ApiField.USERS_IDS: take_with_default(users_ids, []),
            ApiField.APP_VERSION: app_version,
            ApiField.IS_BRANCH: is_branch,
            ApiField.TASK_NAME: task_name,
            ApiField.RESTART_POLICY: restart_policy,
            ApiField.PROXY_KEEP_URL: proxy_keep_url,
            ApiField.ADVANCED_SETTINGS: advanced_settings,
        }
        if len(redirect_requests) > 0:
            data[ApiField.REDIRECT_REQUESTS] = redirect_requests

        if app_id is not None:
            data[ApiField.APP_ID] = app_id
        if module_id is not None:
            data[ApiField.MODULE_ID] = module_id
        resp = self._api.post(method="tasks.run.app", data=data)
        task = resp.json()[0]
        if "id" not in task:
            task["id"] = task.get("taskId")
        return task

    def stop(self, id: int):
        """stop"""
        response = self._api.post("tasks.stop", {ApiField.ID: id})
        return self.Status(response.json()[ApiField.STATUS])

    def get_import_files_list(self, id: int) -> Union[Dict, None]:
        """get_import_files_list"""
        response = self._api.post("tasks.import.files_list", {ApiField.ID: id})
        return response.json() if (response is not None) else None

    def download_import_file(self, id, file_path, save_path):
        """download_import_file"""
        response = self._api.post(
            "tasks.import.download_file",
            {ApiField.ID: id, ApiField.FILENAME: file_path},
            stream=True,
        )

        ensure_base_path(save_path)
        with open(save_path, "wb") as fd:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                fd.write(chunk)

    def create_task_detached(self, workspace_id: int, task_type: Optional[str] = None):
        """create_task_detached"""
        response = self._api.post(
            "tasks.run.python",
            {
                ApiField.WORKSPACE_ID: workspace_id,
                ApiField.SCRIPT: "xxx",
                ApiField.ADVANCED: {ApiField.IGNORE_AGENT: True},
            },
        )
        return response.json()[ApiField.TASK_ID]

    def submit_logs(self, logs) -> None:
        """submit_logs"""
        response = self._api.post("tasks.logs.add", {ApiField.LOGS: logs})
        # return response.json()[ApiField.TASK_ID]

    def upload_files(
        self,
        task_id: int,
        abs_paths: List[str],
        names: List[str],
        progress_cb: Optional[Union[tqdm, Callable]] = None,
    ) -> None:
        """upload_files"""
        if len(abs_paths) != len(names):
            raise RuntimeError("Inconsistency: len(abs_paths) != len(names)")

        hashes = []
        if len(abs_paths) == 0:
            return

        hash_to_items = defaultdict(list)
        hash_to_name = defaultdict(list)
        for idx, item in enumerate(zip(abs_paths, names)):
            path, name = item
            item_hash = get_file_hash(path)
            hashes.append(item_hash)
            hash_to_items[item_hash].append(path)
            hash_to_name[item_hash].append(name)

        unique_hashes = set(hashes)
        remote_hashes = self._api.image.check_existing_hashes(list(unique_hashes))
        new_hashes = unique_hashes - set(remote_hashes)

        # @TODO: upload remote hashes
        if len(remote_hashes) != 0:
            files = []
            for hash in remote_hashes:
                for name in hash_to_name[hash]:
                    files.append({ApiField.NAME: name, ApiField.HASH: hash})
            for batch in batched(files):
                resp = self._api.post(
                    "tasks.files.bulk.add-by-hash",
                    {ApiField.TASK_ID: task_id, ApiField.FILES: batch},
                )
        if progress_cb is not None:
            progress_cb(len(remote_hashes))

        for batch in batched(list(zip(abs_paths, names, hashes))):
            content_dict = OrderedDict()
            for idx, item in enumerate(batch):
                path, name, hash = item
                if hash in remote_hashes:
                    continue
                content_dict["{}".format(idx)] = json.dumps({"fullpath": name, "hash": hash})
                content_dict["{}-file".format(idx)] = (name, open(path, "rb"), "")

            if len(content_dict) > 0:
                encoder = MultipartEncoder(fields=content_dict)
                resp = self._api.post("tasks.files.bulk.upload", encoder)
                if progress_cb is not None:
                    progress_cb(len(content_dict))

    # {
    #     data: {my_val: 1}
    #     obj: {val: 1, res: 2}
    # }
    # {
    #     obj: {new_val: 1}
    # }
    # // apped: true, recursive: false
    # {
    #     data: {my_val: 1}
    #     obj: {new_val: 1}
    # }(edited)
    # // append: false, recursive: false
    # {
    #     obj: {new_val: 1}
    # }(edited)
    #
    # 16: 32
    # // append: true, recursive: true
    # {
    #     data: {my_val: 1}
    #     obj: {val: 1, res: 2, new_val: 1}
    # }

    def set_fields(self, task_id: int, fields: List) -> Dict:
        """set_fields"""
        for idx, obj in enumerate(fields):
            for key in [ApiField.FIELD, ApiField.PAYLOAD]:
                if key not in obj:
                    raise KeyError("Object #{} does not have field {!r}".format(idx, key))
        data = {ApiField.TASK_ID: task_id, ApiField.FIELDS: fields}
        resp = self._api.post("tasks.data.set", data)
        return resp.json()

    def set_fields_from_dict(self, task_id: int, d: Dict) -> Dict:
        """set_fields_from_dict"""
        fields = []
        for k, v in d.items():
            fields.append({ApiField.FIELD: k, ApiField.PAYLOAD: v})
        return self.set_fields(task_id, fields)

    def set_field(
        self,
        task_id: int,
        field: Dict,
        payload: Dict,
        append: Optional[bool] = False,
        recursive: Optional[bool] = False,
    ) -> Dict:
        """set_field"""
        fields = [
            {
                ApiField.FIELD: field,
                ApiField.PAYLOAD: payload,
                ApiField.APPEND: append,
                ApiField.RECURSIVE: recursive,
            }
        ]
        return self.set_fields(task_id, fields)

    def get_fields(self, task_id, fields: List):
        """get_fields"""
        data = {ApiField.TASK_ID: task_id, ApiField.FIELDS: fields}
        resp = self._api.post("tasks.data.get", data)
        return resp.json()["result"]

    def get_field(self, task_id: int, field: str):
        """get_field"""
        result = self.get_fields(task_id, [field])
        return result[field]

    def _validate_checkpoints_support(self, task_id):
        """_validate_checkpoints_support"""
        # pylint: disable=too-few-format-args
        info = self.get_info_by_id(task_id)
        if info["type"] != str(TaskApi.PluginTaskType.TRAIN):
            raise RuntimeError(
                "Task (id={!r}) has type {!r}. "
                "Checkpoints are available only for tasks of type {!r}".format()
            )

    def list_checkpoints(self, task_id: int):
        """list_checkpoints"""
        self._validate_checkpoints_support(task_id)
        resp = self._api.post("tasks.checkpoints.list", {ApiField.ID: task_id})
        return resp.json()

    def delete_unused_checkpoints(self, task_id: int) -> Dict:
        """delete_unused_checkpoints"""
        self._validate_checkpoints_support(task_id)
        resp = self._api.post("tasks.checkpoints.clear", {ApiField.ID: task_id})
        return resp.json()

    def _set_output(self):
        """_set_output"""
        pass

    def set_output_project(
        self,
        task_id: int,
        project_id: int,
        project_name: Optional[str] = None,
        project_preview: Optional[str] = None,
    ) -> Dict:
        """set_output_project"""
        if project_name is None:
            project = self._api.project.get_info_by_id(project_id, raise_error=True)
            project_name = project.name
            project_preview = project.image_preview_url

        output = {ApiField.PROJECT: {ApiField.ID: project_id, ApiField.TITLE: project_name}}
        if project_preview is not None:
            output[ApiField.PROJECT][ApiField.PREVIEW] = project_preview
        resp = self._api.post(
            "tasks.output.set", {ApiField.TASK_ID: task_id, ApiField.OUTPUT: output}
        )
        return resp.json()

    def set_output_report(
        self,
        task_id: int,
        file_id: int,
        file_name: str,
        description: Optional[str] = "Report",
    ) -> Dict:
        """set_output_report"""
        return self._set_custom_output(
            task_id,
            file_id,
            file_name,
            description=description,
            icon="zmdi zmdi-receipt",
        )

    def _set_custom_output(
        self,
        task_id,
        file_id,
        file_name,
        file_url=None,
        description="File",
        icon="zmdi zmdi-file-text",
        color="#33c94c",
        background_color="#d9f7e4",
        download=False,
    ):
        """_set_custom_output"""
        if file_url is None:
            file_url = self._api.file.get_url(file_id)

        output = {
            ApiField.GENERAL: {
                "icon": {
                    "className": icon,
                    "color": color,
                    "backgroundColor": background_color,
                },
                "title": file_name,
                "titleUrl": file_url,
                "download": download,
                "description": description,
            }
        }
        resp = self._api.post(
            "tasks.output.set", {ApiField.TASK_ID: task_id, ApiField.OUTPUT: output}
        )
        return resp.json()

    def set_output_archive(
        self, task_id: int, file_id: int, file_name: str, file_url: Optional[str] = None
    ) -> Dict:
        """set_output_archive"""
        if file_url is None:
            file_url = self._api.file.get_info_by_id(file_id).storage_path
        return self._set_custom_output(
            task_id,
            file_id,
            file_name,
            file_url=file_url,
            description="Download archive",
            icon="zmdi zmdi-archive",
            download=True,
        )

    def set_output_file_download(
        self,
        task_id: int,
        file_id: int,
        file_name: str,
        file_url: Optional[str] = None,
        download: Optional[bool] = True,
    ) -> Dict:
        """set_output_file_download"""
        if file_url is None:
            file_url = self._api.file.get_info_by_id(file_id).storage_path
        return self._set_custom_output(
            task_id,
            file_id,
            file_name,
            file_url=file_url,
            description="Download file",
            icon="zmdi zmdi-file",
            download=download,
        )

    def send_request(
        self,
        task_id: int,
        method: str,
        data: Dict,
        context: Optional[Dict] = {},
        skip_response: bool = False,
        timeout: Optional[int] = 60,
        outside_request: bool = True,
        retries: int = 10,
        raise_error: bool = False,
    ):
        """send_request"""
        if type(data) is not dict:
            raise TypeError("data argument has to be a dict")
        context["outside_request"] = outside_request
        resp = self._api.post(
            "tasks.request.direct",
            {
                ApiField.TASK_ID: task_id,
                ApiField.COMMAND: method,
                ApiField.CONTEXT: context,
                ApiField.STATE: data,
                "skipResponse": skip_response,
                "timeout": timeout,
            },
            retries=retries,
            raise_error=raise_error,
        )
        return resp.json()

    def set_output_directory(self, task_id, file_id, directory_path):
        """set_output_directory"""
        return self._set_custom_output(
            task_id,
            file_id,
            directory_path,
            description="Directory",
            icon="zmdi zmdi-folder",
        )

    def update_meta(
        self,
        id: int,
        data: dict,
        agent_storage_folder: str = None,
        relative_app_dir: str = None,
    ):
        """
        Update given task metadata
        :param id: int — task id
        :param data: dict — meta data to update
        """
        if type(data) == dict:
            data.update({"id": id})
            if agent_storage_folder is None and relative_app_dir is not None:
                raise ValueError(
                    "Both arguments (agent_storage_folder and relative_app_dir) has to be defined or None"
                )
            if agent_storage_folder is not None and relative_app_dir is None:
                raise ValueError(
                    "Both arguments (agent_storage_folder and relative_app_dir) has to be defined or None"
                )
            if agent_storage_folder is not None and relative_app_dir is not None:
                data["agentStorageFolder"] = {
                    "hostDir": agent_storage_folder,
                    "folder": relative_app_dir,
                }

        self._api.post("tasks.meta.update", data)

    def _update_app_content(self, task_id: int, data_patch: List[Dict] = None, state: Dict = None):
        payload = {}
        if data_patch is not None and len(data_patch) > 0:
            payload[ApiField.DATA] = data_patch
        if state is not None and len(state) > 0:
            payload[ApiField.STATE] = state

        resp = self._api.post(
            "tasks.app-v2.data.set",
            {ApiField.TASK_ID: task_id, ApiField.PAYLOAD: payload},
        )
        return resp.json()

    def set_output_error(
        self,
        task_id: int,
        title: str,
        description: Optional[str] = None,
        show_logs: Optional[bool] = True,
    ) -> Dict:
        """
        Set custom error message to the task output.

        :param task_id: Application task ID.
        :type task_id: int
        :param title: Error message to be displayed in the task output.
        :type title: str
        :param description: Description to be displayed in the task output.
        :type description: Optional[str]
        :param show_logs: If True, the link to the task logs will be displayed in the task output.
        :type show_logs: Optional[bool], default True
        :return: Response JSON.
        :rtype: Dict
        :Usage example:

         .. code-block:: python

            import os
            from dotenv import load_dotenv

            import supervisely as sly

            # Load secrets and create API object from .env file (recommended)
            # Learn more here: https://developer.supervisely.com/getting-started/basics-of-authentication
            if sly.is_development():
               load_dotenv(os.path.expanduser("~/supervisely.env"))
            api = sly.Api.from_env()

            task_id = 12345
            title = "Something went wrong"
            description = "Please check the task logs"
            show_logs = True
            api.task.set_output_error(task_id, title, description, show_logs)
        """

        output = {
            ApiField.GENERAL: {
                "icon": {
                    "className": "zmdi zmdi-alert-octagon",
                    "color": "#ff83a6",
                    "backgroundColor": "#ffeae9",
                },
                "title": title,
                "showLogs": show_logs,
                "isError": True,
            }
        }

        if description is not None:
            output[ApiField.GENERAL]["description"] = description

        resp = self._api.post(
            "tasks.output.set",
            {ApiField.TASK_ID: task_id, ApiField.OUTPUT: output},
        )
        return resp.json()

    def set_output_text(
        self,
        task_id: int,
        title: str,
        description: Optional[str] = None,
        show_logs: Optional[bool] = False,
        zmdi_icon: Optional[str] = "zmdi-comment-alt-text",
        icon_color: Optional[str] = "#33c94c",
        background_color: Optional[str] = "#d9f7e4",
    ) -> Dict:
        """
        Set custom text message to the task output.

        :param task_id: Application task ID.
        :type task_id: int
        :param title: Text message to be displayed in the task output.
        :type title: str
        :param description: Description to be displayed in the task output.
        :type description: Optional[str]
        :param show_logs: If True, the link to the task logs will be displayed in the task output.
        :type show_logs: Optional[bool], default False
        :param zmdi_icon: Icon class name from Material Design Icons (ZMDI).
        :type zmdi_icon: Optional[str], default "zmdi-comment-alt-text"
        :param icon_color: Icon color in HEX format.
        :type icon_color: Optional[str], default "#33c94c" (nearest Duron Jolly Green)
        :param background_color: Background color in HEX format.
        :type background_color: Optional[str], default "#d9f7e4" (Cosmic Latte)
        :return: Response JSON.
        :rtype: Dict
        :Usage example:

        .. code-block:: python

            import os
            from dotenv import load_dotenv

            import supervisely as sly

            # Load secrets and create API object from .env file (recommended)
            # Learn more here: https://developer.supervisely.com/getting-started/basics-of-authentication
            if sly.is_development():
            load_dotenv(os.path.expanduser("~/supervisely.env"))
            api = sly.Api.from_env()

            task_id = 12345
            title = "Task is finished"
            api.task.set_output_text(task_id, title)
        """

        output = {
            ApiField.GENERAL: {
                "icon": {
                    "className": f"zmdi {zmdi_icon}",
                    "color": icon_color,
                    "backgroundColor": background_color,
                },
                "title": title,
                "showLogs": show_logs,
                "isError": False,
            }
        }

        if description is not None:
            output[ApiField.GENERAL]["description"] = description

        resp = self._api.post(
            "tasks.output.set",
            {ApiField.TASK_ID: task_id, ApiField.OUTPUT: output},
        )
        return resp.json()

    def update_status(
        self,
        task_id: int,
        status: Status,
    ) -> None:
        """Sets the specified status for the task.

        :param task_id: Task ID in Supervisely.
        :type task_id: int
        :param status: Task status to set.
        :type status: One of the values from :class:`Status`, e.g. Status.FINISHED, Status.ERROR, etc.
        :raises ValueError: If the status value is not allowed.
        """
        # If status was passed without converting to string, convert it.
        # E.g. Status.FINISHED -> "finished"
        status = str(status)
        if status not in self.Status.values():
            raise ValueError(
                f"Invalid status value: {status}. Allowed values: {self.Status.values()}"
            )
        self._api.post("tasks.status.update", {ApiField.ID: task_id, ApiField.STATUS: status})

    def set_output_experiment(self, task_id: int, experiment_info: dict) -> Dict:
        """
        Sets output for the task with experiment info.

        :param task_id: Task ID in Supervisely.
        :type task_id: int
        :param experiment_info: Experiment info from TrainApp.
        :type experiment_info: dict
        :return: None
        :rtype: :class:`NoneType`

        Example of experiment_info:

            experiment_info = {
                'experiment_name': '247_Lemons_RT-DETRv2-M',
                'framework_name': 'RT-DETRv2',
                'model_name': 'RT-DETRv2-M',
                'task_type': 'object detection',
                'project_id': 76,
                'task_id': 247,
                'model_files': {'config': 'model_config.yml'},
                'checkpoints': ['checkpoints/best.pth', 'checkpoints/checkpoint0025.pth', 'checkpoints/checkpoint0050.pth', 'checkpoints/last.pth'],
                'best_checkpoint': 'best.pth',
                'export': {'ONNXRuntime': 'export/best.onnx'},
                'app_state': 'app_state.json',
                'model_meta': 'model_meta.json',
                'train_val_split': 'train_val_split.json',
                'train_size': 4,
                'val_size': 2,
                'hyperparameters': 'hyperparameters.yaml',
                'hyperparameters_id': 45234,
                'artifacts_dir': '/experiments/76_Lemons/247_RT-DETRv2/',
                'datetime': '2025-01-22 18:13:43',
                'evaluation_report_id': 12961,
                'evaluation_report_link': 'https://app.supervisely.com/model-benchmark?id=12961',
                'evaluation_metrics': {
                    'mAP': 0.994059405940594,
                    'AP50': 1.0, 'AP75': 1.0,
                    'f1': 0.9944444444444445,
                    'precision': 0.9944444444444445,
                    'recall': 0.9944444444444445,
                    'iou': 0.9726227736959404,
                    'classification_accuracy': 1.0,
                    'calibration_score': 0.8935745942476048,
                    'f1_optimal_conf': 0.500377893447876,
                    'expected_calibration_error': 0.10642540575239527,
                    'maximum_calibration_error': 0.499622106552124
                },
                'primary_metric': 'mAP'
                'logs': {
                    'type': 'tensorboard',
                    'link': '/experiments/76_Lemons/247_RT-DETRv2/logs/'
                },
            }
        """
        output = {
            ApiField.EXPERIMENT: {ApiField.DATA: {**experiment_info}},
        }
        resp = self._api.post(
            "tasks.output.set", {ApiField.TASK_ID: task_id, ApiField.OUTPUT: output}
        )
        return resp.json()

    def deploy_model_from_api(self, task_id, deploy_params):
        self.send_request(
            task_id,
            "deploy_from_api",
            data={"deploy_params": deploy_params},
            raise_error=True,
        )

    def deploy_model_app(
        self,
        module_id: int,
        workspace_id: int,
        agent_id: Optional[int] = None,
        description: Optional[str] = "application description",
        params: Dict[str, Any] = None,
        log_level: Optional[Literal["info", "debug", "warning", "error"]] = "info",
        users_ids: Optional[List[int]] = None,
        app_version: Optional[str] = "",
        is_branch: Optional[bool] = False,
        task_name: Optional[str] = "pythonSpawned",
        restart_policy: Optional[Literal["never", "on_error"]] = "never",
        proxy_keep_url: Optional[bool] = False,
        redirect_requests: Optional[Dict[str, int]] = {},
        limit_by_workspace: bool = False,
        deploy_params: Dict[str, Any] = None,
        timeout: int = 100,
    ):
        if deploy_params is None:
            deploy_params = {}
        task_info = self.start(
            agent_id=agent_id,
            workspace_id=workspace_id,
            module_id=module_id,
            description=description,
            params=params,
            log_level=log_level,
            users_ids=users_ids,
            app_version=app_version,
            is_branch=is_branch,
            task_name=task_name,
            restart_policy=restart_policy,
            proxy_keep_url=proxy_keep_url,
            redirect_requests=redirect_requests,
            limit_by_workspace=limit_by_workspace,
        )

        attempt_delay_sec = 10
        attempts = (timeout + attempt_delay_sec) // attempt_delay_sec
        ready = self._api.app.wait_until_ready_for_api_calls(
            task_info["id"], attempts, attempt_delay_sec
        )
        if not ready:
            raise TimeoutError(
                f"Task {task_info['id']} is not ready for API calls after {timeout} seconds."
            )
        logger.info("Deploying model from API")
        self.deploy_model_from_api(task_info["id"], deploy_params=deploy_params)
        return task_info

    def deploy_custom_model(
        self,
        workspace_id: int,
        artifacts_dir: str,
        checkpoint_name: str = None,
        agent_id: int = None,
        device: str = "cuda",
    ) -> int:
        """
        Deploy a custom model based on the artifacts directory.

        :param workspace_id: Workspace ID in Supervisely.
        :type workspace_id: int
        :param artifacts_dir: Path to the artifacts directory.
        :type artifacts_dir: str
        :param checkpoint_name: Checkpoint name (with extension) to deploy.
        :type checkpoint_name: Optional[str]
        :param agent_id: Agent ID in Supervisely.
        :type agent_id: Optional[int]
        :param device: Device string (default is "cuda").
        :type device: str
        :raises ValueError: if validations fail.
        """
        from dataclasses import asdict

        from supervisely.nn.artifacts import (
            RITM,
            RTDETR,
            Detectron2,
            MMClassification,
            MMDetection,
            MMDetection3,
            MMSegmentation,
            UNet,
            YOLOv5,
            YOLOv5v2,
            YOLOv8,
        )
        from supervisely.nn.experiments import get_experiment_info_by_artifacts_dir
        from supervisely.nn.utils import ModelSource, RuntimeType

        if not isinstance(workspace_id, int) or workspace_id <= 0:
            raise ValueError(f"workspace_id must be a positive integer. Received: {workspace_id}")
        if not isinstance(artifacts_dir, str) or not artifacts_dir.strip():
            raise ValueError("artifacts_dir must be a non-empty string.")

        workspace_info = self._api.workspace.get_info_by_id(workspace_id)
        if workspace_info is None:
            raise ValueError(f"Workspace with ID '{workspace_id}' not found.")

        team_id = workspace_info.team_id
        logger.debug(
            f"Starting model deployment. Team: {team_id}, Workspace: {workspace_id}, Artifacts Dir: '{artifacts_dir}'"
        )

        # Train V1 logic (if artifacts_dir does not start with '/experiments')
        if not artifacts_dir.startswith("/experiments"):
            logger.debug("Deploying model from Train V1 artifacts")
            frameworks = {
                "/detectron2": Detectron2,
                "/mmclassification": MMClassification,
                "/mmdetection": MMDetection,
                "/mmdetection-3": MMDetection3,
                "/mmsegmentation": MMSegmentation,
                "/RITM_training": RITM,
                "/RT-DETR": RTDETR,
                "/unet": UNet,
                "/yolov5_train": YOLOv5,
                "/yolov5_2.0_train": YOLOv5v2,
                "/yolov8_train": YOLOv8,
            }

            framework_cls = next(
                (cls for prefix, cls in frameworks.items() if artifacts_dir.startswith(prefix)),
                None,
            )
            if not framework_cls:
                raise ValueError(f"Unsupported framework for artifacts_dir: '{artifacts_dir}'")

            framework = framework_cls(team_id)
            if framework_cls is RITM or framework_cls is YOLOv5:
                raise ValueError(
                    f"{framework.framework_name} framework is not supported for deployment"
                )

            logger.debug(f"Detected framework: '{framework.framework_name}'")

            module_id = self._api.app.get_ecosystem_module_id(framework.serve_slug)
            serve_app_name = framework.serve_app_name
            logger.debug(f"Module ID fetched:' {module_id}'. App name: '{serve_app_name}'")

            train_info = framework.get_info_by_artifacts_dir(artifacts_dir.rstrip("/"))
            if not hasattr(train_info, "checkpoints") or not train_info.checkpoints:
                raise ValueError("No checkpoints found in train info.")

            checkpoint = None
            if checkpoint_name is not None:
                for cp in train_info.checkpoints:
                    if cp.name == checkpoint_name:
                        checkpoint = cp
                        break
                if checkpoint is None:
                    raise ValueError(f"Checkpoint '{checkpoint_name}' not found in train info.")
            else:
                logger.debug("Checkpoint name not provided. Using the last checkpoint.")
                checkpoint = train_info.checkpoints[-1]

            checkpoint_name = checkpoint.name
            deploy_params = {
                "device": device,
                "model_source": ModelSource.CUSTOM,
                "task_type": train_info.task_type,
                "checkpoint_name": checkpoint_name,
                "checkpoint_url": checkpoint.path,
            }

            if getattr(train_info, "config_path", None) is not None:
                deploy_params["config_url"] = train_info.config_path

            if framework.require_runtime:
                deploy_params["runtime"] = RuntimeType.PYTORCH

        else:  # Train V2 logic (when artifacts_dir starts with '/experiments')
            logger.debug("Deploying model from Train V2 artifacts")

            def get_framework_from_artifacts_dir(artifacts_dir: str) -> str:
                clean_path = artifacts_dir.rstrip("/")
                parts = clean_path.split("/")
                if not parts or "_" not in parts[-1]:
                    raise ValueError(f"Invalid artifacts_dir format: '{artifacts_dir}'")
                return parts[-1].split("_", 1)[1]

            # TODO: temporary solution, need to add Serve App Name into config.json
            framework_name = get_framework_from_artifacts_dir(artifacts_dir)
            logger.debug(f"Detected framework: {framework_name}")

            modules = self._api.app.get_list_all_pages(
                method="ecosystem.list",
                data={"filter": [], "search": framework_name, "categories": ["serve"]},
                convert_json_info_cb=lambda x: x,
            )
            if not modules:
                raise ValueError(f"No serve apps found for framework: '{framework_name}'")

            module = modules[0]
            module_id = module["id"]
            serve_app_name = module["name"]
            logger.debug(f"Serving app delected: '{serve_app_name}'. Module ID: '{module_id}'")

            experiment_info = get_experiment_info_by_artifacts_dir(
                self._api, team_id, artifacts_dir
            )
            if not experiment_info:
                raise ValueError(
                    f"Failed to retrieve experiment info for artifacts_dir: '{artifacts_dir}'"
                )

            if len(experiment_info.checkpoints) == 0:
                raise ValueError(f"No checkpoints found in: '{artifacts_dir}'.")

            checkpoint = None
            if checkpoint_name is not None:
                for checkpoint_path in experiment_info.checkpoints:
                    if get_file_name_with_ext(checkpoint_path) == checkpoint_name:
                        checkpoint = get_file_name_with_ext(checkpoint_path)
                        break
                if checkpoint is None:
                    raise ValueError(
                        f"Provided checkpoint '{checkpoint_name}' not found. Using the best checkpoint."
                    )
            else:
                logger.debug("Checkpoint name not provided. Using the best checkpoint.")
                checkpoint = experiment_info.best_checkpoint

            checkpoint_name = checkpoint
            deploy_params = {
                "device": device,
                "model_source": ModelSource.CUSTOM,
                "model_files": {
                    "checkpoint": f"{experiment_info.artifacts_dir}checkpoints/{checkpoint_name}"
                },
                "model_info": asdict(experiment_info),
                "runtime": RuntimeType.PYTORCH,
            }
            # TODO: add support for **kwargs

            config = experiment_info.model_files.get("config")
            if config is not None:
                deploy_params["model_files"]["config"] = f"{experiment_info.artifacts_dir}{config}"
                logger.debug(f"Config file added: {experiment_info.artifacts_dir}{config}")

        logger.info(
            f"{serve_app_name} app deployment started. Checkpoint: '{checkpoint_name}'. Deploy params: '{deploy_params}'"
        )
        task_info = self.deploy_model_app(
            module_id,
            workspace_id,
            agent_id,
            description=f"Deployed via deploy_custom_model",
            task_name=f"{serve_app_name} ({checkpoint_name})",
            deploy_params=deploy_params,
        )
        if task_info is None:
            raise RuntimeError(f"Failed to run '{serve_app_name}'.")
        return task_info["id"]
