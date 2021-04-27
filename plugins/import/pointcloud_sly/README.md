# Import Pointclouds with annotations in Supervisely format 
This plugin allows you to upload Pointcloud Projects in Supervisely format which includes pointclouds, annotations and `meta.json`. You can download example [here](https://drive.google.com/file/d/1BtZyffWtWNR-mk_PHNPMnGgSlAkkQpBl/view?usp=sharing).

# Example:

For this format the structure of directory should be the following:

```
my_project
├── ds0
│   ├── ann
│   │   ├── frame.pcd.json
│   │   └── kitti_0000000001.pcd.json
│   ├── pointcloud
│   │   ├── frame.pcd
│   │   └── kitti_0000000001.pcd
│   └── related_images
│       ├── frame_pcd
│       │   ├── 0000000000.png
│       │   └── 0000000000.png.json
│       └── kitti_0000000001_pcd
│           ├── 0000000000.png
│           └── 0000000000.png.json
├── key_id_map.json
└── meta.json
```


Project directory `my_project` contains single dataset `ds0`, file `key_id_map.json` that maps supervisely ids to uniq keys, and file `meta.json` with information about project classes and tags.

Dataset folder consists of annotation folder `ann`, folder with pointcloud files in `.pcd` format and optional folder `related_images`. Items in these directories can be matched by names. 