#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Serve the plant database through a REST API.
"""
import argparse
import json
import os

from flask import Flask
from flask import request
from flask import send_file
from flask import send_from_directory
from flask_cors import CORS
from flask_restful import Api
from flask_restful import Resource

from plantdb import io
from plantdb import webcache
from plantdb.fsdb import FSDB as DB


def parsing():
    parser = argparse.ArgumentParser(description='Serve the plant database through a REST API.')
    parser.add_argument('-db', '--db_location', type=str, default="",
                        help='Local database to serve.')
    parser.add_argument('-prefix', '--db_prefix', type=str, default="",
                        help='Prefix to use with the database.')
    return parser


def fmt_date(scan):
    try:
        x = scan.id
        date, time = x.split('_')
        time = time.replace('-', ':')
    except:
        date, time = "01-01-00", "00:00:00"
    return "%s %s" % (date, time)


def compute_fileset_matches(scan):
    filesets_matches = {}
    for fs in scan.get_filesets():
        x = fs.id.split('_')[0]
        filesets_matches[x] = fs.id
    return filesets_matches


def get_path(f):
    fs = f.fileset
    scan = fs.scan
    return os.path.join(db_prefix, scan.id, fs.id, f.filename)


def fmt_scan_minimal(scan):
    metadata = scan.get_metadata()
    try:
        species = metadata['object']['species']
    except:
        species = "N/A"
    try:
        environment = metadata['object']['environment']
    except:
        environment = "N/A"
    try:
        plant = metadata['object']['plant_id']
    except:
        plant = "N/A"

    n_photos = len(scan.get_fileset('images').get_files())

    fileset_visu = scan.get_fileset("Visualization")
    files_metadata = fileset_visu.get_metadata("files")
    first_thumbnail_path = get_path(fileset_visu.get_file(files_metadata["thumbnails"][0]))
    print(files_metadata["zip"])

    has_mesh = files_metadata["mesh"] is not None
    has_point_cloud = files_metadata["point_cloud"] is not None
    has_pcd_groundTruth = files_metadata["pcd_ground_truth"] is not None
    has_skeleton = files_metadata["skeleton"] is not None
    has_angles = files_metadata["angles"] is not None
    has_segmentation2D = files_metadata["segmentation2d_evaluation"] is not None
    has_segmentedPcd_evaluation = files_metadata["segmented_pcd_evaluation"] is not None
    has_point_cloud_evaluation = files_metadata["point_cloud_evaluation"] is not None
    has_manual_measures = "measures" in metadata or files_metadata["measures"] is not None
    has_segmented_point_cloud = len([f.id for f in scan.get_filesets() if 'SegmentedPointCloud' in f.id]) > 0

    return {
        "id": scan.id,
        "metadata": {
            "date": fmt_date(scan),
            "species": species,
            "plant": plant,
            "environment": environment,
            "nbPhotos": n_photos,
            "files": {
                "metadatas": os.path.join(db_prefix, scan.id, "metadata/metadata.json"),
                "archive": get_path(fileset_visu.get_file(files_metadata["zip"]))
            }
        },
        "thumbnailUri": first_thumbnail_path,
        "hasMesh": has_mesh,
        "hasPointCloud": has_point_cloud,
        "hasPcdGroundTruth": has_pcd_groundTruth,
        "hasSkeleton": has_skeleton,
        "hasAngleData": has_angles,
        "hasSegmentation2D": has_segmentation2D,
        "hasSegmentedPcdEvaluation": has_segmentedPcd_evaluation,
        "hasPointCloudEvaluation": has_point_cloud_evaluation,
        "hasManualMeasures": has_manual_measures,
        "hasAutomatedMeasures": has_angles,
        "hasSegmentedPointCloud": has_segmented_point_cloud
    }


def fmt_scans(scans, query):
    res = []
    for scan in scans:
        filesets_matches = compute_fileset_matches(scan)
        if 'Visualization' in filesets_matches:
            metadata = scan.get_metadata()
            if query is not None and not (query.lower() in json.dumps(metadata).lower()):
                continue
            res.append(fmt_scan_minimal(scan))
    return res


def fmt_scan(scan):
    fileset_visu = scan.get_fileset("Visualization")
    files_metadata = fileset_visu.get_metadata("files")

    res = fmt_scan_minimal(scan)
    metadata = scan.get_metadata()

    files_uri = {}
    if (res["hasMesh"]):
        files_uri["mesh"] = get_path(fileset_visu.get_file(files_metadata["mesh"]))
    if (res["hasPointCloud"]):
        files_uri["pointCloud"] = get_path(fileset_visu.get_file(files_metadata["point_cloud"]))
    if (res["hasPcdGroundTruth"]):
        files_uri["pcdGroundTruth"] = get_path(fileset_visu.get_file(files_metadata["pcd_ground_truth"]))

    res["filesUri"] = files_uri
    res["data"] = {}

    if (res["hasSkeleton"]):
        x = io.read_json(fileset_visu.get_file(files_metadata["skeleton"]))
        res["data"]["skeleton"] = x

    if (res["hasSegmentation2D"]):
        x = io.read_json(fileset_visu.get_file(files_metadata["segmentation2d_evaluation"]))
        res["data"]["segmentation2D"] = x

    if (res["hasSegmentedPcdEvaluation"]):
        x = io.read_json(fileset_visu.get_file(files_metadata["segmented_pcd_evaluation"]))
        res["data"]["segmentedPcdEvaluation"] = x

    if (res["hasPointCloudEvaluation"]):
        x = io.read_json(fileset_visu.get_file(files_metadata["point_cloud_evaluation"]))
        res["data"]["pointCloudEvaluation"] = x

    if (res["hasAngleData"]):
        x = io.read_json(fileset_visu.get_file(files_metadata["angles"]))
        if "fruit_points" not in x:
            x["fruit_points"] = []
        res["data"]["angles"] = x

        if res["hasManualMeasures"]:
            try:
                res["data"]["angles"]["measured_angles"] = metadata["measures"]["angles"]
            except KeyError:
                measures = io.read_json(fileset_visu.get_file(files_metadata["measures"]))
                res["data"]["angles"]["measured_angles"] = measures["angles"]

            try:
                res["data"]["angles"]["measured_internodes"] = metadata["measures"]["internodes"]
            except KeyError:
                measures = io.read_json(fileset_visu.get_file(files_metadata["measures"]))
                res["data"]["angles"]["measured_internodes"] = measures["internodes"]

    # backward compatibility
    try:
        # old version
        res["workspace"] = metadata["scanner"]["workspace"]
    except KeyError:
        # new version
        camera_model = io.read_json(fileset_visu.get_file(files_metadata["camera"]))
        res["workspace"] = camera_model["bounding_box"]

    res["camera"] = {}

    # backward compatibility
    try:
        # old version
        res["camera"]["model"] = metadata["computed"]["camera_model"]
    except KeyError:
        # new version
        camera_model = io.read_json(fileset_visu.get_file(files_metadata["camera"]))
        res["camera"]["model"] = camera_model["1"]

    res["camera"]["poses"] = []

    poses = io.read_json(fileset_visu.get_file(files_metadata["poses"]))

    for i, im in enumerate(files_metadata["images"]):
        f = fileset_visu.get_file(im)
        id = f.get_metadata("image_id")
        for k in poses.keys():
            if os.path.splitext(poses[k]['name'])[0] == id:
                res['camera']['poses'].append({
                    'id': id,
                    'tvec': poses[k]['tvec'],
                    'rotmat': poses[k]['rotmat'],
                    'photoUri': get_path(f),
                    'thumbnailUri': get_path(fileset_visu.get_file(files_metadata["thumbnails"][i]))})
                break
    return res


class ScanList(Resource):
    def get(self):
        query = request.args.get('filterQuery')
        scans = fmt_scans(db.get_scans(), query=query)
        return scans


class Scan(Resource):
    def get(self, scan_id):
        scan = db.get_scan(scan_id)
        return fmt_scan(scan)


class File(Resource):
    def get(self, path):
        return send_from_directory(db_location, path)


class Refresh(Resource):
    def get(self):
        global db
        db.disconnect()
        db.connect()
        return 200


class Image(Resource):
    """Class representing a image HTTP request, subclass of
    flask_restful's Resource class.
    """

    def get(self, scanid, filesetid, fileid):
        """Return the HTTP response with the image data. Resize the image if
        necessary.
        """
        global db
        size = request.args.get('size', default='thumb', type=str)
        if not size in ['orig', 'thumb', 'large']:
            size = 'thumb'
        path = webcache.image_path(db, scanid, filesetid, fileid, size)
        return send_file(path, mimetype='image/jpeg')


class PointCloud(Resource):
    """Class representing a point cloud HTTP request, subclass of
    flask_restful's Resource class.
    """

    def get(self, scanid, filesetid, fileid):
        """Return the HTTP response with the point cloud data. Downsample the
        point cloud if necessary.
        """
        global db
        size = request.args.get('size', default='preview', type=str)
        if not size in ['orig', 'preview']:
            size = 'preview'
        path = webcache.pointcloud_path(db, scanid, filesetid, fileid, size)
        return send_file(path, mimetype='application/octet-stream')


class PointCloudGroundTruth(Resource):
    """Class representing a point cloud HTTP request, subclass of
    flask_restful's Resource class.
    """

    def get(self, scanid, filesetid, fileid):
        """Return the HTTP response with the point cloud data. Downsample the
        point cloud if necessary.
        """
        global db
        size = request.args.get('size', default='preview', type=str)
        if not size in ['orig', 'preview']:
            size = 'preview'
        path = webcache.pointcloud_path(db, scanid, filesetid, fileid, size)
        return send_file(path, mimetype='application/octet-stream')


class Mesh(Resource):
    """Class representing a mesh HTTP request, subclass of
    flask_restful's Resource class.
    """

    def get(self, scanid, filesetid, fileid):
        """Return the HTTP response with the mesh data. Downsample the
        mesh if necessary.
        """
        global db
        size = request.args.get('size', default='orig', type=str)
        if not size in ['orig']:
            size = 'orig'
        path = webcache.mesh_path(db, scanid, filesetid, fileid, size)
        return send_file(path, mimetype='application/octet-stream')


def run():
    parser = parsing()
    args = parser.parse_args()

    app = Flask(__name__)
    CORS(app)
    api = Api(app)

    global db_location
    global db_prefix

    if args.db_location == "":
        try:
            db_location = os.environ["DB_LOCATION"]
        except:
            raise ValueError("DB_LOCATION environment variable is not set")
    else:
        db_location = args.db_location

    if args.db_prefix == "":
        try:
            db_prefix = os.environ["DB_PREFIX"]
        except:
            db_prefix = "/files/"

    global db
    db = DB(db_location)
    db.connect()

    print("n scans = %i" % len(db.get_scans()))

    api.add_resource(ScanList, '/scans')
    api.add_resource(Scan, '/scans/<scan_id>')
    api.add_resource(File, '/files/<path:path>')
    api.add_resource(Refresh, '/refresh')
    api.add_resource(Image, '/image/<string:scanid>/<string:filesetid>/<string:fileid>')
    api.add_resource(PointCloud, '/pointcloud/<string:scanid>/<string:filesetid>/<string:fileid>')
    api.add_resource(PointCloudGroundTruth, '/pcGroundTruth/<string:scanid>/<string:filesetid>/<string:fileid>')
    api.add_resource(Mesh, '/mesh/<string:scanid>/<string:filesetid>/<string:fileid>')

    app.run(host='0.0.0.0')


if __name__ == '__main__':
    run()
