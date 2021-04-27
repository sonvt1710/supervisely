# coding: utf-8

import os
import json
import glob
import cv2
import numpy as np

import SimpleITK as sitk

import pydicom
from pydicom.multival import MultiValue
from pydicom.pixel_data_handlers.util import convert_color_space

import supervisely_lib as sly


class WrongInputDataStructure(Exception):
    pass


def get_datasets_names_and_paths():
    result = [(os.path.relpath(dir_name, sly.TaskPaths.DATA_DIR).replace('/', '__'), dir_name)
              for dir_name, _, file_names in os.walk(sly.TaskPaths.DATA_DIR) if len(file_names) > 0]
    all_ds_names = {x[0] for x in result}
    for idx, ds_with_dir in enumerate(result):
        if ds_with_dir[0] == '.':
            for candidate_suffix in range(1, len(all_ds_names) + 2):
                candidate_name = 'ds' + str(candidate_suffix)
                if candidate_name not in all_ds_names:
                    result[idx] = (candidate_name, ds_with_dir[1])
                    break
            break
    return result


def get_tags_from_dicom_object(dicom_obj, requested_tags):
    results = []
    for tag_name in requested_tags:
        tag_value = getattr(dicom_obj, tag_name, None)
        if tag_value is not None:
            tag_meta = sly.TagMeta(tag_name, sly.TagValueType.ANY_STRING)
            tag = sly.Tag(tag_meta, str(tag_value))
            results.append((tag, tag_meta))
    return results


def get_rescale_params(ds):
    """
    For pixels brightness scale and offset.
    """
    rescale_intercept = getattr(ds, 'RescaleIntercept', 0.0)
    rescale_slope = getattr(ds, 'RescaleSlope', 1.0)
    return rescale_intercept, rescale_slope


def get_LUT_value(data, window, level, rescale_intercept=0, rescale_slope=1):
    if isinstance(window, list) or isinstance(window, MultiValue):
        window = window[0]
    if isinstance(level, list) or isinstance(level, MultiValue):
        level = int(level[0])

    # some vendors use wrong rescale intercept and slope?
    if rescale_slope == 0 and rescale_intercept == 1:
        rescale_slope = 1
        rescale_intercept = 0

    m_w = window - 1
    m_l = level - 0.5

    rescaled_data = (data * rescale_slope) + rescale_intercept
    cond_list = [rescaled_data <= (m_l - m_w / 2), rescaled_data > (m_l + m_w / 2)]
    func_list = [0, 255, lambda v: ((v - m_l) / m_w + 0.5) * (255 - 0)]
    return np.piecewise(rescaled_data, cond_list, func_list)


def prepare_dicom_image(im_arr, dicom_obj):
    try:  # In some DICOM files, necessary attributes are lost.
        rescale_intercept, rescale_slope = get_rescale_params(dicom_obj)
        img = get_LUT_value(im_arr, dicom_obj.WindowWidth, dicom_obj.WindowCenter, rescale_intercept, rescale_slope)
        img = img.astype(np.uint8)
    except AttributeError:  # Common approach
        img = im_arr.astype(np.float32)
        img = np.round(255.0 / img.max() * img)
        img = img.clip(0, 255)
        img = img.astype(np.uint8)

    if len(img.shape) == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    return img


def extract_images_from_dicom(dicom_obj, filepath):
    itk_img = sitk.ReadImage(filepath)
    pixel_array = sitk.GetArrayViewFromImage(itk_img)

    #pixel_array = dicom_obj.pixel_array
    interpretation_str = str(getattr(dicom_obj, 'PhotometricInterpretation', None))
    if interpretation_str in ('YBR_FULL_422', 'YBR_FULL'):
        pixel_array = convert_color_space(pixel_array, interpretation_str, 'RGB')
    dcm_channels = pixel_array.shape

    images = []
    if (len(dcm_channels) > 3 and dcm_channels[-1] == 3) or (len(dcm_channels) == 3 and dcm_channels[-1] != 3):
        for i in range(dcm_channels[0]):
            images.append(prepare_dicom_image(pixel_array[i], dicom_obj))
    else:
        images.append(prepare_dicom_image(pixel_array, dicom_obj))
    return images


def convert():
    settings = json.load(open(sly.TaskPaths.TASK_CONFIG_PATH))
    tag_metas = sly.TagMetaCollection()

    out_project = sly.Project(os.path.join(sly.TaskPaths.RESULTS_DIR, settings['res_names']['project']), sly.OpenMode.CREATE)
    requested_tags = settings.get("options", {}).get("tags", [])

    if len(requested_tags) != len(set(requested_tags)):
        raise ValueError('Duplicate values detected in the list of requested tags: {}'.format(requested_tags))

    skipped_count = 0
    samples_count = 0

    for ds_name, folder_path in get_datasets_names_and_paths():
        dataset = None

        # Process all files in current folder
        filenames_in_folder = sly.fs.list_files(folder_path)
        dataset_progress = sly.Progress('Dataset {!r}'.format(ds_name), len(filenames_in_folder))

        for dicom_filename in filenames_in_folder:
            try:
                # Read DICOM file
                dicom_obj = pydicom.dcmread(dicom_filename)

                # Extract tags
                tags_and_metas = get_tags_from_dicom_object(dicom_obj, requested_tags)

                # Extract images (DICOM file may contain few images)
                base_name = os.path.basename(dicom_filename)
                images = extract_images_from_dicom(dicom_obj, dicom_filename)

                for image_index, image in enumerate(images):
                    sample_name = base_name
                    if len(images) > 1:
                        sample_name = base_name + '__{:04d}'.format(image_index)

                    samples_count += 1
                    ann = sly.Annotation(img_size=image.shape[:2])

                    # Save tags
                    for tag, tag_meta in tags_and_metas:
                        ann = ann.add_tag(tag)
                        if tag_meta not in tag_metas:
                            tag_metas = tag_metas.add(tag_meta)

                    # Save annotations
                    if dataset is None:
                        dataset = out_project.create_dataset(ds_name)
                    dataset.add_item_np(sample_name + '.png', image, ann=ann)

            except Exception as e:
                exc_str = str(e)
                sly.logger.warn('Input sample skipped due to error: {}'.format(exc_str), exc_info=True, extra={
                    'exc_str': exc_str,
                    'dataset_name': ds_name,
                    'image_name': dicom_filename,
                })
                skipped_count += 1

            dataset_progress.iter_done_report()

    sly.logger.info('Processed.', extra={'samples': samples_count, 'skipped': skipped_count})

    if out_project.total_items == 0:
        raise RuntimeError('Result project is empty! All input DICOM files have unreadable format!')

    out_meta = sly.ProjectMeta(tag_metas=tag_metas)
    out_project.set_meta(out_meta)


def main():
    convert()
    sly.report_import_finished()


if __name__ == '__main__':
    #@TODO: for debug
    #sly.fs.clean_dir(sly.TaskPaths.RESULTS_DIR)
    sly.main_wrapper('DICOM_TO_IMAGES_IMPORT', main)
