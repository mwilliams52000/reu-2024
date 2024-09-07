#!/usr/bin/env python3

import rospy
import time
import numpy as np
import sensor_msgs.point_cloud2 as pc2
from sensor_msgs.msg import PointCloud2
import matplotlib.pyplot as plt
from scipy.spatial import KDTree

# Constructs a 2D Traversability Map and then 
# returns it to the waypoint path node for use with 
# the advanced RRT Star Path Planner.

class TraversabilityListener:
    def __init__(self, scale_value):
        self.points_list = []
        self.scale_value = int(scale_value)
        self.terrain_points_list = []
        self.traversability_values = None
        self.travs_x = None
        self.travs_y = None

        # Subscribe to the /traversability_map topic
        rospy.Subscriber("/trav_map", PointCloud2, self.callback_classes)
    
    # Pointcloud callback
    def callback_classes(self, point_cloud):
        self.cloud_points = pc2.read_points(point_cloud, skip_nans=True)
        self.points_list = list(self.cloud_points)

    # Get the traversability value of a point
    def extract_trav_value(self, point):
        return point[3]
    
    # Generate an empty map in the case where a traversability map cannot be constructed
    def generate_empty_map(self, width, height):
        return np.random.uniform(low=1, high=1, size=(width,height))
    
    def controller(self):
        travs_result = self.build_traversability_map()
        map_q1 = travs_result[0]
        map_q2 = travs_result[1]
        map_q3 = travs_result[2]
        map_q4 = travs_result[3]
        return map_q1, map_q2, map_q3, map_q4
    
    # Optimize the quadrants to build the traversability maps for the planner
    def optimize_quadrants(self, map_q1, map_q2, map_q3, map_q4):
        # Create a KDTree for the points
        points_array = np.array(self.points_list)
        kdtree = KDTree(points_array[:, :2])

        min_trav = min(point[3] for point in self.points_list)
        max_trav = max(point[3] for point in self.points_list)

        # Process each quadrant
        def process_quadrant(map_q, x_multiplier, y_multiplier):
            # Iterate through each element in the map
            for (x, y), element in np.ndenumerate(map_q):
                # Get a list of colors from within each block of the 2D array
                x_value = (x * x_multiplier) / self.scale_value
                y_value = (y * y_multiplier) / self.scale_value

                box_min = np.array([x_value, y_value])
                box_max = np.array([x_value + 1, y_value + 1])

                indices = kdtree.query_ball_point((box_min + box_max) / 2, np.linalg.norm(box_max - box_min) / 2)
                relevant_points = points_array[indices]

                if len(relevant_points) > 0:
                    traversability_values = [self.extract_trav_value(point) for point in relevant_points]
                    avg_trav = sum(traversability_values) / len(traversability_values)
                    normalized_trav = (avg_trav - min_trav) / (max_trav - min_trav)
                    map_q[y, x] = normalized_trav

        # Start timer to construct traversability map
        start_time = time.time()
        try:
            print("Scaling traversability map for the path planner...")
            process_quadrant(map_q1, 1, 1)
            process_quadrant(map_q2, -1, 1)
            process_quadrant(map_q3, -1, -1)
            process_quadrant(map_q4, 1, -1)
            current_time = time.time() - start_time
            print("It took", current_time, "seconds to scale the traversability map for the planner.")
        except Exception as e:
            print("There was a problem:", e)
            current_time = time.time() - start_time
            print("Process ran for", current_time, "seconds.")

    # Build the traversability map
    def build_traversability_map(self):
        scale_value = self.scale_value
        points_list = self.points_list
        x_coords = [point[0] for point in points_list]
        y_coords = [point[1] for point in points_list]

        if len(x_coords) > 0 and len(y_coords) > 0:
            min_x, max_x = min(x_coords), max(x_coords)
            min_y, max_y = min(y_coords), max(y_coords)
            traversability_values = []
            
            # Initialize empty maps for each quadrant
            # These are the traversability maps to be passed to the planner
            result = self.initialize_empty_quadrants(min_x, max_x, min_y, max_y, scale_value, 0.0)
            map_q1, map_q2, map_q3, map_q4 = result

            # Extract traversability values and create colormap
            traversability_values = traversability_values = [self.extract_trav_value(point) for point in points_list]
            min_trav, max_trav = min(traversability_values), max(traversability_values)

            # Normalize traversability values to a range of [0, 1]
            normalized_values = [(v - min_trav) / (max_trav - min_trav) for v in traversability_values]

            # Create colormap
            cmap = plt.cm.viradis  

            # Plotting
            scatter = plt.scatter(x_coords, y_coords, c=normalized_values, cmap=cmap, s=10, alpha=0.8)
            plt.colorbar(scatter, label='Normalized Traversability Value')
            plt.colorbar(label='Normalized Traversability Value')
            plt.title('Traversability Map')
            plt.xlabel('X')
            plt.ylabel('Y')
            plt.grid(True)
            plt.show()

            # Build the traversability map for the planner
            self.optimize_quadrants(map_q1, map_q2, map_q3, map_q4)

            return map_q1, map_q2, map_q3, map_q4
        else:
            print("No valid points found in the point cloud")
            return None, None, None, None
    
    #Function to initialize empty quadrant maps
    def initialize_empty_quadrants(self, min_x, max_x, min_y, max_y, scale_value, initial_value):
        if (min_y > 0 and max_y > 0 and min_x > 0 and max_x > 0):
            map_q1 = np.full((scale_value * int(max_y) + 1, scale_value * int(max_x) + 1), initial_value)
            map_q2 = np.full((scale_value * int(max_y) + 1, scale_value * int(max_x) + 1), initial_value)
            map_q3 = np.full((scale_value * int(max_y) + 1, scale_value * int(max_x) + 1), initial_value)
            map_q4 = np.full((scale_value * int(max_y) + 1, scale_value * int(max_x) + 1), initial_value)
        elif (min_y > 0 and max_y > 0 and max_x <= 0):
            map_q1 = np.full((scale_value * int(max_y) + 1, scale_value * int(abs(min_x) + 1)), initial_value)
            map_q2 = np.full((scale_value * int(max_y) + 1, scale_value * int(abs(min_x) + 1)), initial_value)
            map_q3 = np.full((scale_value * int(max_y) + 1, scale_value * int(abs(min_x) + 1)), initial_value)
            map_q4 = np.full((scale_value * int(max_y) + 1, scale_value * int(abs(min_x) + 1)), initial_value)
        elif (max_y <= 0 and min_x > 0 and max_x > 0):
            map_q1 = np.full((scale_value * int(abs(min_y) + 1), scale_value * int(max_x) + 1), initial_value)
            map_q2 = np.full((scale_value * int(abs(min_y) + 1), scale_value * int(max_x) + 1), initial_value)
            map_q3 = np.full((scale_value * int(abs(min_y) + 1), scale_value * int(max_x) + 1), initial_value)
            map_q4 = np.full((scale_value * int(abs(min_y) + 1), scale_value * int(max_x) + 1), initial_value)
        elif (min_y > 0 and max_y > 0 and min_x <= 0 and max_x > 0):
            map_q1 = np.full((scale_value * int(max_y) + 1, scale_value * int(max_x - min_x) + 1), initial_value)
            map_q2 = np.full((scale_value * int(max_y) + 1, scale_value * int(max_x - min_x) + 1), initial_value)
            map_q3 = np.full((scale_value * int(max_y) + 1, scale_value * int(max_x - min_x) + 1), initial_value)
            map_q4 = np.full((scale_value * int(max_y) + 1, scale_value * int(max_x - min_x) + 1), initial_value)
        elif (min_y <= 0 and max_y > 0 and min_x > 0 and max_x > 0):
            map_q1 = np.full((scale_value * int(max_y - min_y) + 1, scale_value * int(max_x) + 1), initial_value)
            map_q2 = np.full((scale_value * int(max_y - min_y) + 1, scale_value * int(max_x) + 1), initial_value)
            map_q3 = np.full((scale_value * int(max_y - min_y) + 1, scale_value * int(max_x) + 1), initial_value)
            map_q4 = np.full((scale_value * int(max_y - min_y) + 1, scale_value * int(max_x) + 1), initial_value)
        elif (max_y > 0 and max_x > 0):
            map_q1 = np.full((scale_value * int(max_y - min_y) + 1, scale_value * int(max_x - min_x) + 1), initial_value)
            map_q2 = np.full((scale_value * int(max_y - min_y) + 1, scale_value * int(max_x - min_x) + 1), initial_value)
            map_q3 = np.full((scale_value * int(max_y - min_y) + 1, scale_value * int(max_x - min_x) + 1), initial_value)
            map_q4 = np.full((scale_value * int(max_y - min_y) + 1, scale_value * int(max_x - min_x) + 1), initial_value)
        elif max_y <= 0 and max_x > 0:
            map_q1 = np.full((scale_value * int(abs(min_y) + 1), scale_value * int(max_x - min_x) + 1), initial_value)
            map_q2 = np.full((scale_value * int(abs(min_y) + 1), scale_value * int(max_x - min_x) + 1), initial_value)
            map_q3 = np.full((scale_value * int(abs(min_y) + 1), scale_value * int(max_x - min_x) + 1), initial_value)
            map_q4 = np.full((scale_value * int(abs(min_y) + 1), scale_value * int(max_x - min_x) + 1), initial_value)
        elif max_y <= 0 and max_x <= 0:
            map_q1 = np.full((scale_value * int(abs(min_y) + 1), scale_value * int(abs(min_x) + 1)), initial_value)
            map_q2 = np.full((scale_value * int(abs(min_y) + 1), scale_value * int(abs(min_x) + 1)), initial_value)
            map_q3 = np.full((scale_value * int(abs(min_y) + 1), scale_value * int(abs(min_x) + 1)), initial_value)
            map_q4 = np.full((scale_value * int(abs(min_y) + 1), scale_value * int(abs(min_x) + 1)), initial_value)
        elif max_y > 0 and max_x <= 0:
            map_q1 = np.full((scale_value * int(max_y - min_y) + 1, scale_value * int(abs(min_x))), initial_value)
            map_q2 = np.full((scale_value * int(max_y - min_y) + 1, scale_value * int(abs(min_x))), initial_value)
            map_q3 = np.full((scale_value * int(max_y - min_y) + 1, scale_value * int(abs(min_x))), initial_value)
            map_q4 = np.full((scale_value * int(max_y - min_y) + 1, scale_value * int(abs(min_x))), initial_value)
        return map_q1, map_q2, map_q3, map_q4