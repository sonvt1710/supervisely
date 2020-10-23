import supervisely_lib as sly

#!!!!! Note: fields labelerLogin, createdAt, createdAt, id, classId - can be IGNORED
ann_json = {
  "description": "",
  "tags": [],
  "size": {
    "height": 800,
    "width": 1067
  },
  "objects": [
    {
      "id": 2173919,
      "classId": 4379,
      "description": "",
      "geometryType": "rectangle",
      "labelerLogin": "admin",
      "createdAt": "2020-10-23T14:09:48.860Z",
      "updatedAt": "2020-10-23T14:09:52.306Z",
      "tags": [],
      "classTitle": "banana",
      "points": {
        "exterior": [
          [
            584,
            364
          ],
          [
            902,
            541
          ]
        ],
        "interior": []
      }
    },
    {
      "id": 2173920,
      "classId": 4379,
      "description": "",
      "geometryType": "rectangle",
      "labelerLogin": "admin",
      "createdAt": "2020-10-23T14:09:52.214Z",
      "updatedAt": "2020-10-23T14:09:52.214Z",
      "tags": [],
      "classTitle": "banana",
      "points": {
        "exterior": [
          [
            609,
            104
          ],
          [
            769,
            290
          ]
        ],
        "interior": []
      }
    }
  ]
}


api = sly.Api.from_env()

image_id = 353689

api.annotation.upload_json(image_id, ann_json)