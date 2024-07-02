#!/usr/bin/env python3
import rospy
import numpy as np
from sensor_msgs.msg import PointCloud2
import sensor_msgs.point_cloud2 as pc2
import open3d as o3d
from scipy.spatial import cKDTree

class PointCloudStitcher:
    def __init__(self):
        self.pointcloud_sub = rospy.Subscriber('/segmented_pointcloud', PointCloud2, self.pointcloud_callback)
        self.liosam_map_sub = rospy.Subscriber('/lio_sam/mapping/map_global', PointCloud2, self.liosam_map_callback)
        self.stitched_pointcloud_pub = rospy.Publisher('/stitched_pointcloud', PointCloud2, queue_size=10)
        self.global_pointcloud = None
        self.liosam_map = None
        self.liosam_tree = None
        self.voxel_size = 0.5  # 25cm voxel size, adjust as needed
        self.distance_threshold = 0.5  # 10cm threshold for point matching

    def liosam_map_callback(self, map_msg):
        self.liosam_map = self.pointcloud2_to_array(map_msg)
        self.liosam_tree = cKDTree(self.liosam_map[:, :3])

    def pointcloud_callback(self, pointcloud_msg):
        if self.liosam_tree is None:
            rospy.logwarn("LIO-SAM map not received yet. Skipping this point cloud.")
            return
        
        local_pointcloud = self.pointcloud2_to_array(pointcloud_msg)
        self.update_global_pointcloud(local_pointcloud)
        self.publish_stitched_pointcloud(pointcloud_msg.header)

    def update_global_pointcloud(self, new_pointcloud):
        # Filter new_pointcloud based on LIO-SAM map
        distances, _ = self.liosam_tree.query(new_pointcloud[:, :3])
        filtered_pointcloud = new_pointcloud[distances < self.distance_threshold]

        if self.global_pointcloud is None:
            self.global_pointcloud = filtered_pointcloud
        else:
            # Combine with existing global pointcloud
            self.global_pointcloud = np.vstack((self.global_pointcloud, filtered_pointcloud))

        # Downsample the combined pointcloud
        self.global_pointcloud = self.voxel_downsample(self.global_pointcloud)

    def voxel_downsample(self, pointcloud):
        pcd = o3d.geometry.PointCloud()
        pcd.points = o3d.utility.Vector3dVector(pointcloud[:, :3])
        pcd.colors = o3d.utility.Vector3dVector(pointcloud[:, 3:])
        downsampled_pcd = pcd.voxel_down_sample(self.voxel_size)
        return np.hstack([np.asarray(downsampled_pcd.points), np.asarray(downsampled_pcd.colors)])

    def publish_stitched_pointcloud(self, header):
        header.frame_id = 'map'  # Ensure the stitched pointcloud is in the map frame
        #downsampled_global = self.voxel_downsample(self.global_pointcloud)
        fields = [pc2.PointField('x', 0, pc2.PointField.FLOAT32, 1),
                  pc2.PointField('y', 4, pc2.PointField.FLOAT32, 1),
                  pc2.PointField('z', 8, pc2.PointField.FLOAT32, 1),
                  pc2.PointField('r', 12, pc2.PointField.FLOAT32, 1),
                  pc2.PointField('g', 16, pc2.PointField.FLOAT32, 1),
                  pc2.PointField('b', 20, pc2.PointField.FLOAT32, 1)]
        pointcloud_msg = pc2.create_cloud(header, fields, self.global_pointcloud)
        self.stitched_pointcloud_pub.publish(pointcloud_msg)

    @staticmethod
    def pointcloud2_to_array(cloud_msg):
        points_list = []
        for point in pc2.read_points(cloud_msg, skip_nans=True, field_names=("x", "y", "z", "r", "g", "b")):
            points_list.append(point)
        return np.array(points_list, dtype=np.float32)

if __name__ == '__main__':
    rospy.init_node('pointcloud_stitcher_node', anonymous=True)
    stitcher = PointCloudStitcher()
    rospy.spin()