# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

# <pep8 compliant>


import json
from os import path

import bpy
from bpy.props import EnumProperty
from bpy.types import Operator

from .export_preset import export_scene


class ExportObject:
    def __init__(self, ob):
        self.ob = ob
        self.hide_select = ob.hide_select
        self.hide_set = ob.hide_get()
        self.hide_viewport = ob.hide_viewport
        self.select_set = ob.select_get()

    def restore(self):
        self.ob.hide_select = self.hide_select
        self.ob.hide_set(self.hide_set)
        self.ob.hide_viewport = self.hide_viewport
        self.ob.select_set(self.select_set)

    def prepare(self):
        self.ob.hide_select = False
        self.ob.hide_set(False)
        self.ob.hide_viewport = False
        self.ob.select_set(True)


class ExportCollection:
    def __init__(self, col):
        self.col = col
        self.layer_collection = self.get_view_layer_collection(
            bpy.context.view_layer.layer_collection, self.col)
        self.l_exclude = self.layer_collection.exclude
        self.l_hide_viewport = self.layer_collection.hide_viewport
        self.hide_select = self.col.hide_select
        self.hide_viewport = self.col.hide_viewport

    def restore(self):
        self.layer_collection.exclude = self.l_exclude
        self.layer_collection.hide_viewport = self.l_hide_viewport
        self.col.hide_select = self.hide_select
        self.col.hide_viewport = self.hide_viewport

    def prepare(self):
        self.layer_collection.exclude = False
        self.layer_collection.hide_viewport = False
        self.col.hide_select = False
        self.col.hide_viewport = False

    def get_view_layer_collection(self, layer_collection, collection):
        if layer_collection.collection == collection:
            return layer_collection

        for child_layer in layer_collection.children:
            view_layer_collection = self.get_view_layer_collection(
                child_layer, collection)

            if view_layer_collection is not None:
                return view_layer_collection


class ET_OT_export_single(Operator):
    """Export selected objects in a single file"""
    bl_idname = "export_toolset.single_export"
    bl_label = "Export Single"

    @classmethod
    def poll(cls, context):
        selected_objects = context.selected_objects
        active_collection = context.collection
        active_object = context.active_object
        export_properties = None

        if len(selected_objects) == 0:
            export_properties = active_collection.export_properties
        elif active_object:
            export_properties = active_object.export_properties

        return (export_properties and
                export_properties.directory != "")

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')

        selected_objects = context.selected_objects
        active_collection = context.collection
        active_object = context.active_object

        if len(selected_objects) == 0:
            export_properties = active_collection.export_properties
            export_mode = 'COLLECTION'
        elif active_collection:
            export_properties = active_object.export_properties
            export_mode = 'OBJECT'

        file_name = active_object.name if export_mode == 'OBJECT' else active_collection.name
        directory = export_properties.directory

        if path.exists(directory):
            scene = context.scene

            if scene.ET_reset_pos is True:
                bpy.ops.view3d.snap_cursor_to_selected()
                c_loс = scene.cursor.location.copy()
                bpy.ops.view3d.snap_cursor_to_center()
                bpy.ops.view3d.snap_selected_to_cursor(use_offset=True)

            if scene.ET_reset_rot is True:
                rots = []
                for ob in context.selected_objects:
                    rots.append(ob.rotation_euler.copy())
                    ob.rotation_euler.zero()

            export_format = export_properties.format.lower()

            if export_format == "fbx":
                export_preset = export_properties.fbx_preset
            elif export_format == "obj":
                export_preset = export_properties.obj_preset

            use_collection = False if export_mode == 'OBJECT' else True

            # Select all objects inside collections
            self.export_objects = []
            self.export_cols = []

            if use_collection:
                self.select_objects(active_collection)

            # Export
            result = export_scene(
                directory, file_name, export_preset, export_format)

            # Restore objects restrictions
            for ob in self.export_objects:
                ob.restore()

            for col in self.export_cols:
                col.restore()

            if scene.ET_reset_pos is True:
                scene.cursor.location = c_loс
                bpy.ops.view3d.snap_selected_to_cursor(use_offset=True)

            if scene.ET_reset_rot is True:
                i = 0
                for ob in context.selected_objects:
                    ob.rotation_euler = rots[i]
                    i = i + 1

            self.report({'INFO'}, result)
            return {'FINISHED'}
        else:
            self.report({'ERROR'}, "Export Path Doesn't Exist!")
            return {'FINISHED'}

    def select_objects(self, collection):
        export_col = ExportCollection(collection)
        self.export_cols.append(export_col)

        for col in collection.children:
            self.select_objects(col)

        export_col.prepare()

        for ob in collection.objects:
            export_ob = ExportObject(ob)
            self.export_objects.append(export_ob)
            export_ob.prepare()


class ET_OT_export_batch(Operator):
    """Export each selected object in a separate file"""
    bl_idname = "export_toolset.export_batch"
    bl_label = "Export Batch"

    @classmethod
    def poll(cls, context):
        selected_objects = context.selected_objects

        if (len(selected_objects) > 1):
            for obj in selected_objects:
                if obj.export_properties.directory == "":
                    return False

            return True

        return False

    def execute(self, context):
        selected_objects = context.selected_objects
        bpy.ops.object.select_all(action='DESELECT')

        for obj in selected_objects:
            obj.select_set(True)
            context.view_layer.objects.active = obj
            export_properties = obj.export_properties
            directory = export_properties.directory

            if path.exists(directory):
                export_format = export_properties.format.lower()

                if export_format == "fbx":
                    export_preset = export_properties.fbx_preset
                elif export_format == "obj":
                    export_preset = export_properties.obj_preset

                result = export_scene(
                    directory, obj.name, export_preset, export_format)

                self.report({'INFO'}, result)
            else:
                self.report({'ERROR'}, "Export Path Doesn't Exist!")

        for obj in selected_objects:
            obj.select_set(True)

        return {'FINISHED'}


class ET_OT_sync_dir_path(Operator):
    """Set active directory to each selected object"""
    bl_idname = "export_toolset.sync_dir_path"
    bl_label = "Synchronize Directories"

    @classmethod
    def poll(cls, context):
        return (len(context.selected_objects) > 1 and
                context.active_object and
                context.active_object.export_properties.directory)

    def execute(self, context):
        active_object = context.active_object

        if active_object.export_properties.directory:
            for obj in context.selected_objects:
                obj.export_properties.directory = active_object.export_properties.directory

        return {'FINISHED'}


class ET_OT_export_linked_data(Operator):
    """ Export transformation data for each linked object into JSON file """
    bl_idname = "export_toolset.export_linked_data"
    bl_label = "Export Linked Data"

    @classmethod
    def poll(cls, context):
        return (context.active_object and
                context.active_object.export_properties.directory and
                len(context.selected_objects) > 0)

    def execute(self, context):
        bpy.ops.object.select_all(action='DESELECT')
        bpy.ops.object.select_linked(type='OBDATA')

        active_object = context.active_object
        name = active_object.name.rsplit('.', 1)[0]
        file_path = path.join(active_object.export_properties.directory,
                              name + ".json")

        # Clear file
        open(file_path, 'w').close()

        with open(file_path, 'a') as file:
            data = {"Linked Transform Data": []}

            for obj in context.selected_objects:
                loc = obj.location
                rot = obj.rotation_euler
                size = obj.dimensions

                obj_data = {obj.name: {
                    "location": {"x": loc.x, "y": loc.y, "z": loc.z},
                    "rotation": {"x": rot.x, "y": rot.y, "z": rot.z},
                    "size": {"x": size.x, "y": size.y, "z": size.z}}}

                data["Linked Transform Data"].append(obj_data)

            file.write(json.dumps(data, indent=4) + '\n')

        return {'FINISHED'}
