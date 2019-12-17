"""
This file is part of Giswater 3
The program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the License,
or (at your option) any later version.
"""
# -*- coding: utf-8 -*-
from qgis.core import QgsCategorizedSymbolRenderer, QgsDataSourceUri, QgsFeature, QgsField, QgsGeometry, QgsMarkerSymbol, QgsProject, QgsRendererCategory, QgsSimpleFillSymbolLayer, QgsSymbol, QgsVectorLayer, QgsVectorLayerExporter

from qgis.PyQt.QtCore import QVariant
from qgis.PyQt.QtGui import QColor
from qgis.PyQt.QtWidgets import QTabWidget

import os
from random import randrange
from .. import utils_giswater


class AddLayer(object):

    def __init__(self, iface, settings, controller, plugin_dir):
        # Initialize instance attributes
        self.iface = iface
        self.canvas = self.iface.mapCanvas()
        self.settings = settings
        self.controller = controller
        self.plugin_dir = plugin_dir
        self.dao = self.controller.dao
        self.schema_name = self.controller.schema_name
        self.project_type = None
        self.uri = self.set_uri()


    def set_uri(self):

        uri = QgsDataSourceUri()
        uri.setConnection(self.controller.credentials['host'], self.controller.credentials['port'],
                          self.controller.credentials['db'], self.controller.credentials['user'],
                          self.controller.credentials['password'])
        return uri


    def manage_geometry(self, geometry):
        """ Get QgsGeometry and return as text
         :param geometry: (QgsGeometry)
         """
        geometry = geometry.asWkt().replace('Z (', ' (')
        geometry = geometry.replace(' 0)', ')')
        return geometry


    def from_dxf_to_toc(self, dxf_layer, dxf_output_filename):
        """  Read a dxf file and put result into TOC
        :param dxf_layer: (QgsVectorLayer)
        :param dxf_output_filename: Name of layer into TOC (string)
        :return: dxf_layer (QgsVectorLayer)
        """

        QgsProject.instance().addMapLayer(dxf_layer, False)
        root = QgsProject.instance().layerTreeRoot()
        my_group = root.findGroup(dxf_output_filename)
        if my_group is None:
            my_group = root.insertGroup(0, dxf_output_filename)
        my_group.insertLayer(0, dxf_layer)
        self.canvas.refreshAllLayers()
        return dxf_layer


    def export_layer_to_db(self, layer, crs):
        """ Export layer to postgres database
        :param layer: (QgsVectorLayer)
        :param crs: QgsVectorLayer.crs() (crs)
        """
        sql = f'DROP TABLE "{layer.name()}";'
        self.controller.execute_sql(sql, log_sql=True)

        schema_name = self.controller.credentials['schema'].replace('"', '')

        self.uri.setDataSource(schema_name, layer.name(), None, "", layer.name())

        error = QgsVectorLayerExporter.exportLayer(layer, self.uri.uri(), self.controller.credentials['user'], crs, False)

        if error[0] != 0:
            self.controller.log_info(F"ERROR --> {error[1]}")


    def from_postgres_to_toc(self, tablename=None, the_geom="the_geom", field_id="id",  child_layers=None, group='GW Layers'):
        """ Put selected layer into TOC
        :param tablename: Postgres table name (string)
        :param the_geom: Geometry field of the table (string)
        :param field_id: Field id of the table (string)
        :param child_layers: List of layers (stringList)
        :param group: Name of the group that will be created in the toc (string)
        """

        schema_name = self.controller.credentials['schema'].replace('"', '')
        if child_layers is not None:
            for layer in child_layers:
                if layer[0] != 'Load all':
                    self.uri.setDataSource(schema_name, f'{layer[0]}', the_geom, None, layer[1] + "_id")
                    vlayer = QgsVectorLayer(self.uri.uri(), f'{layer[0]}', "postgres")
                    self.check_for_group(vlayer, group)
        else:
            self.uri.setDataSource(schema_name, f'{tablename}', the_geom, None, field_id)
            vlayer = QgsVectorLayer(self.uri.uri(), f'{tablename}', "postgres")
            self.check_for_group(vlayer, group)
        self.iface.mapCanvas().refresh()


    def check_for_group(self, layer, group=None):
        """ If the function receives a group name, check if it exists or not and put the layer in this group
        :param layer: (QgsVectorLayer)
        :param group: Name of the group that will be created in the toc (string)
        """

        if group is None:
            QgsProject.instance().addMapLayer(layer)
        else:
            root = QgsProject.instance().layerTreeRoot()
            my_group = root.findGroup(group)
            if my_group is None:
                my_group = root.insertGroup(0, group)
            my_group.insertLayer(0, layer)


    def add_temp_layer(self, dialog, data, function_name, force_tab=True, reset_text=True, tab_idx=1, del_old_layers=True):
        """ Add QgsVectorLayer into TOC
        :param dialog:
        :param data:
        :param function_name:
        :param force_tab:
        :param reset_text:
        :param tab_idx:
        :param del_old_layers:
        :return:
        """
        if del_old_layers:
            self.delete_layer_from_toc(function_name)
        srid = self.controller.plugin_settings_value('srid')
        for k, v in list(data.items()):
            if str(k) == "info":
                self.populate_info_text(dialog, data, force_tab, reset_text, tab_idx)
            else:
                counter = len(data[k]['values'])
                if counter > 0:
                    counter = len(data[k]['values'])
                    geometry_type = data[k]['geometryType']
                    v_layer = QgsVectorLayer(f"{geometry_type}?crs=epsg:{srid}", function_name, 'memory')
                    self.populate_vlayer(v_layer, data, k, counter)
                    if 'qmlPath' in data[k] and data[k]['qmlPath']:
                        qml_path = data[k]['qmlPath']
                        self.load_qml(v_layer, qml_path)
                    elif 'category_field' in data[k] and data[k]['category_field']:
                        field = data[k]['category_field']
                        size = data[k]['size'] if 'size' in data[k] and data[k]['size'] else 2
                        self.categoryze_layer(v_layer, field, size)


    def categoryze_layer(self, layer, cat_field, size = 2):
        """
        :param layer: QgsVectorLayer to be categorized (QgsVectorLayer)
        :param cat_field: Field to categorize (string)
        """
        cat_field = 'expl_id'
        size = 4
        # get unique values
        fields = layer.fields()
        fni = fields.indexOf(cat_field)
        unique_values = layer.dataProvider().uniqueValues(fni)
        categories = []
        for unique_value in unique_values:
            # initialize the default symbol for this geometry type
            symbol = QgsSymbol.defaultSymbol(layer.geometryType())
            symbol.setSize(size)

            # configure a symbol layer
            # layer_style = {}
            # layer_style['color'] = '%d, %d, %d' % (randrange(0, 256), randrange(0, 256), randrange(0, 256))
            # layer_style['color'] = '255,0,0'
            # layer_style['outline'] = '#000000'
            color = QColor(0, 0, 255)
            if  unique_value == 1:
                color = QColor(255, 0, 0)
            symbol.setColor(color)
            # layer_style['horizontal_anchor_point'] = '6'
            # layer_style['offset_map_unit_scale'] = '6'
            # layer_style['outline_width'] = '6'
            # layer_style['outline_width_map_unit_scale'] = '6'
            # layer_style['size'] = '6'
            # layer_style['size_map_unit_scale'] = '6'
            # layer_style['vertical_anchor_point'] = '6'

            # symbol_layer = QgsSimpleFillSymbolLayer.create(layer_style)
            # print(f"Symbollaye --> {symbol_layer}")
            # # replace default symbol layer with the configured one
            # if symbol_layer is not None:
            #     symbol.changeSymbolLayer(0, symbol_layer)

            # create renderer object
            category = QgsRendererCategory(unique_value, symbol, str(unique_value))
            # entry for the list of category items
            categories.append(category)

            # create renderer object
        renderer = QgsCategorizedSymbolRenderer(cat_field, categories)

        # assign the created renderer to the layer
        if renderer is not None:
            layer.setRenderer(renderer)

        layer.triggerRepaint()
        self.iface.layerTreeView().refreshLayerSymbology(layer.id())


    def populate_info_text(self, dialog, data, force_tab=True, reset_text=True, tab_idx=1):
        """ Populate txt_infolog QTextEdit widget
        :param data: Json
        :param force_tab: Force show tab (boolean)
        :param reset_text: Reset(or not) text for each iteration (boolean)
        :param tab_idx: index of tab to force (integer)
        :return:
        """
        change_tab = False
        text = utils_giswater.getWidgetText(dialog, dialog.txt_infolog, return_string_null=False)

        if reset_text:
            text = ""
        for item in data['info']['values']:
            if 'message' in item:
                if item['message'] is not None:
                    text += str(item['message']) + "\n"
                    if force_tab:
                        change_tab = True
                else:
                    text += "\n"

        utils_giswater.setWidgetText(dialog, 'txt_infolog', text+"\n")
        qtabwidget = dialog.findChild(QTabWidget,'mainTab')
        if change_tab and qtabwidget is not None:
            qtabwidget.setCurrentIndex(tab_idx)

        return change_tab



    def populate_vlayer(self, virtual_layer, data, layer_type, counter):
        """
        :param virtual_layer: Memory QgsVectorLayer (QgsVectorLayer)
        :param data: Json
        :param layer_type: point, line, polygon...(string)
        :param counter: control if json have values (integer)
        :return:
        """
        prov = virtual_layer.dataProvider()

        # Enter editing mode
        virtual_layer.startEditing()
        if counter > 0:
            for key, value in list(data[layer_type]['values'][0].items()):
                # add columns
                if str(key) != 'the_geom':
                    prov.addAttributes([QgsField(str(key), QVariant.String)])

        # Add features
        for item in data[layer_type]['values']:
            attributes = []
            fet = QgsFeature()

            for k, v in list(item.items()):
                if str(k) != 'the_geom':
                    attributes.append(v)
                if str(k) in 'the_geom':
                    sql = f"SELECT St_AsText('{v}')"
                    row = self.controller.get_row(sql, log_sql=False)
                    geometry = QgsGeometry.fromWkt(str(row[0]))
                    fet.setGeometry(geometry)
            fet.setAttributes(attributes)
            prov.addFeatures([fet])

        # Commit changes
        virtual_layer.commitChanges()
        QgsProject.instance().addMapLayer(virtual_layer, False)
        root = QgsProject.instance().layerTreeRoot()
        my_group = root.findGroup('GW Functions results')
        if my_group is None:
            my_group = root.insertGroup(0, 'GW Functions results')

        my_group.insertLayer(0, virtual_layer)


    def delete_layer_from_toc(self, layer_name):
        """ Delete layer from toc if exist
         :param layer_name: Name's layer (string)
         """

        layer = None
        for lyr in list(QgsProject.instance().mapLayers().values()):
            if lyr.name() == layer_name:
                layer = lyr
                break
        if layer is not None:
            QgsProject.instance().removeMapLayer(layer)
            self.delete_layer_from_toc(layer_name)


    def load_qml(self, layer, qml_path):
        """ Apply QML style located in @qml_path in @layer
        :param layer: layer to set qml (QgsVectorLayer)
        :param qml_path: desired path (string)
        """

        if layer is None:
            return False

        if not os.path.exists(qml_path):
            self.controller.log_warning("File not found", parameter=qml_path)
            return False

        if not qml_path.endswith(".qml"):
            self.controller.log_warning("File extension not valid", parameter=qml_path)
            return False

        layer.loadNamedStyle(qml_path)
        layer.triggerRepaint()

        return True