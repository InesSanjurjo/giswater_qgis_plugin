"""
This file is part of Giswater 3
The program is free software: you can redistribute it and/or modify it under the terms of the GNU
General Public License as published by the Free Software Foundation, either version 3 of the License,
or (at your option) any later version.
"""
# -*- coding: utf-8 -*-
import os, psycopg2, psycopg2.extras, subprocess

from functools import partial

from .. import utils_giswater
from .parent import ParentAction
from ..ui_manager import QmGenerator


class I18NGenerator(ParentAction):

    def __init__(self, iface, settings, controller, plugin_dir):
        ParentAction.__init__(self, iface, settings, controller, plugin_dir)
        self.plugin_dir = plugin_dir


    def init_db(self, host, port, db, user, password):
        """ Initializes database connection """

        self.conn = None
        self.cursor = None
        try:
            self.conn = psycopg2.connect(database=db, user=user, port=port, password=password,
                                    host=host)
            self.cursor = self.conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            status = True
        except psycopg2.DatabaseError as e:
            print(f'Connection error: {e}')
            self.last_error = e
            status = False
        return status


    def close_db(self):
        """ Close database connection """

        try:
            status = True
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()
            del self.cursor
            del self.conn
        except Exception as e:
            self.last_error = e
            status = False

        return status


    def init_dialog(self):
        self.dlg_qm = QmGenerator()
        self.load_settings(self.dlg_qm)
        self.load_user_values()

        self.dlg_qm.btn_translate.setEnabled(False)

        self.dlg_qm.btn_connection.clicked.connect(self.check_connection)
        self.dlg_qm.btn_translate.clicked.connect(self.check_translate_options)
        self.dlg_qm.btn_close.clicked.connect(partial(self.close_dialog, self.dlg_qm))
        self.dlg_qm.rejected.connect(self.save_user_values)
        self.dlg_qm.rejected.connect(self.close_db)
        self.open_dialog(self.dlg_qm)

    def check_translate_options(self):
        py_msg = utils_giswater.isChecked(self.dlg_qm, self.dlg_qm.chk_py_msg)
        db_msg = utils_giswater.isChecked(self.dlg_qm, self.dlg_qm.chk_db_msg)
        if py_msg:
            self.create_files_py_message()
        if db_msg:
            self.create_files_db_message()


    def check_connection(self):
        """ Check connection to database """
        self.dlg_qm.cmb_language.clear()
        self.dlg_qm.lbl_info.clear()
        self.close_db()
        host = utils_giswater.getWidgetText(self.dlg_qm, self.dlg_qm.txt_host)
        port = utils_giswater.getWidgetText(self.dlg_qm, self.dlg_qm.txt_port)
        db = utils_giswater.getWidgetText(self.dlg_qm, self.dlg_qm.txt_db)
        user = utils_giswater.getWidgetText(self.dlg_qm, self.dlg_qm.txt_user)
        password = utils_giswater.getWidgetText(self.dlg_qm, self.dlg_qm.txt_pass)
        status = self.init_db(host, port, db, user, password)
        if not status:
            self.dlg_qm.btn_translate.setEnabled(False)
            utils_giswater.setWidgetText(self.dlg_qm, 'lbl_info', self.last_error)
            return
        self.populate_cmb_language()


    def populate_cmb_language(self):
        """ Populate combo with languages values """
        self.dlg_qm.btn_translate.setEnabled(True)
        host = utils_giswater.getWidgetText(self.dlg_qm, self.dlg_qm.txt_host)
        utils_giswater.setWidgetText(self.dlg_qm, 'lbl_info', f'Connected to {host}')
        sql = "SELECT user_language, py_language, xml_language, py_file FROM i18n.cat_language"
        rows = self.get_rows(sql)
        utils_giswater.set_item_data(self.dlg_qm.cmb_language, rows, 0)
        cur_user = self.controller.get_current_user()
        language = self.controller.plugin_settings_value('qm_lang_language' + cur_user)
        utils_giswater.set_combo_itemData(self.dlg_qm.cmb_language, language, 0)


    def save_user_values(self):
        """ Save selected user values """
        host = utils_giswater.getWidgetText(self.dlg_qm, self.dlg_qm.txt_host, return_string_null=False)
        port = utils_giswater.getWidgetText(self.dlg_qm, self.dlg_qm.txt_port, return_string_null=False)
        db = utils_giswater.getWidgetText(self.dlg_qm, self.dlg_qm.txt_db, return_string_null=False)
        user = utils_giswater.getWidgetText(self.dlg_qm, self.dlg_qm.txt_user, return_string_null=False)
        language = utils_giswater.get_item_data(self.dlg_qm, self.dlg_qm.cmb_language, 0)
        py_msg = utils_giswater.isChecked(self.dlg_qm, self.dlg_qm.chk_py_msg)
        db_msg = utils_giswater.isChecked(self.dlg_qm, self.dlg_qm.chk_db_msg)
        cur_user = self.controller.get_current_user()
        self.controller.plugin_settings_set_value('qm_lang_host' + cur_user, host)
        self.controller.plugin_settings_set_value('qm_lang_port' + cur_user, port)
        self.controller.plugin_settings_set_value('qm_lang_db' + cur_user, db)
        self.controller.plugin_settings_set_value('qm_lang_user' + cur_user, user)
        self.controller.plugin_settings_set_value('qm_lang_language' + cur_user, language)
        self.controller.plugin_settings_set_value('qm_lang_py_msg' + cur_user, py_msg)
        self.controller.plugin_settings_set_value('qm_lang_db_msg' + cur_user, db_msg)


    def load_user_values(self):
        """ Load last selected user values
        :return: Dictionary with values
        """
        cur_user = self.controller.get_current_user()
        host = self.controller.plugin_settings_value('qm_lang_host' + cur_user)
        port = self.controller.plugin_settings_value('qm_lang_port' + cur_user)
        db = self.controller.plugin_settings_value('qm_lang_db' + cur_user)
        user = self.controller.plugin_settings_value('qm_lang_user' + cur_user)
        py_msg = self.controller.plugin_settings_value('qm_lang_py_msg' + cur_user)
        db_msg = self.controller.plugin_settings_value('qm_lang_db_msg' + cur_user)
        utils_giswater.setWidgetText(self.dlg_qm, 'txt_host', host)
        utils_giswater.setWidgetText(self.dlg_qm, 'txt_port', port)
        utils_giswater.setWidgetText(self.dlg_qm, 'txt_db', db)
        utils_giswater.setWidgetText(self.dlg_qm, 'txt_user', user)
        utils_giswater.setChecked(self.dlg_qm, self.dlg_qm.chk_py_msg, py_msg)
        utils_giswater.setChecked(self.dlg_qm, self.dlg_qm.chk_db_msg, db_msg)


    def create_files_py_message(self):
        """ Read the values of the database and generate the ts and qm files """
        py_language = utils_giswater.get_item_data(self.dlg_qm, self.dlg_qm.cmb_language, 1)
        xml_language = utils_giswater.get_item_data(self.dlg_qm, self.dlg_qm.cmb_language, 2)
        py_file = utils_giswater.get_item_data(self.dlg_qm, self.dlg_qm.cmb_language, 3)
        key_lbl = f'lb_{py_language}'
        key_tooltip = f'tt_{py_language}'

        # Get python messages values
        sql = f"SELECT source, {py_language} FROM i18n.pymessage;"
        py_messages = self.get_rows(sql)

        # Get ui messages values
        sql = (f"SELECT dialog_name, source, lb_enen, {key_lbl}, tt_eses, {key_tooltip} "
               f" FROM i18n.pydialog "
               f" ORDER BY dialog_name;")
        py_dialogs = self.get_rows(sql)


        ts_path = self.plugin_dir + os.sep + 'i18n' + os.sep + f'giswater_{py_file}.ts'
        # Check if file exist
        if os.path.exists(ts_path):
            msg = "Are you sure you want to overwrite this file?"
            answer = self.controller.ask_question(msg, "Overwrite")
            if not answer:
                return
        ts_file = open(ts_path, "w")

        # Create header
        line = '<?xml version="1.0" encoding="utf-8"?>\n'
        line += '<!DOCTYPE TS>\n'
        line += f'<TS version="2.0" language="{xml_language}">\n'
        line += '\t<!-- PYTHON MESSAGES -->\n'
        # Create children for message
        line += '\t<context>\n'
        line += '\t\t<name>ui_message</name>\n'
        ts_file.write(line)
        for py_msg in py_messages:
            line = f"\t\t<message>\n"
            line += f"\t\t\t<source>{py_msg['source'].rstrip()}</source>\n"
            if py_msg[py_language] is None:
                py_msg[py_language] = py_msg['source']
            line += f"\t\t\t<translation>{py_msg[py_language].rstrip()}</translation>\n"
            line += f"\t\t</message>\n"
            ts_file.write(line)
        line = '\t</context>\n\n'
        line += '\t<!-- UI TRANSLATION -->\n'
        ts_file.write(line)
        # Create children for ui
        name = None
        for py_dlg in py_dialogs:
            print(f"NAME --> {name}, DN --> {py_dlg['dialog_name']}")
            # Create child <context> (ui's name)
            if name and name != py_dlg['dialog_name']:
                print("TEST 20")
                line += '\t</context>\n'
                ts_file.write(line)
            if name != py_dlg['dialog_name']:
                print("TEST 10")
                name = py_dlg['dialog_name']
                line = '\t<context>\n'
                line += f'\t\t<name>{name}</name>\n'
                line += f'\t\t<message>\n'
                line += f'\t\t\t<source>title</source>\n'
                line += f'\t\t\t<translation>{py_dlg[key_lbl]}</translation>\n'
                line += f'\t\t</message>\n'
            # Create child for labels
            line += f"\t\t<message>\n"
            line += f"\t\t\t<source>{py_dlg['source'].rstrip()}</source>\n"
            if py_dlg[key_lbl] is None:
                py_dlg[key_lbl] = py_dlg['lb_enen']
            line += f"\t\t\t<translation>{py_dlg[key_lbl].rstrip()}</translation>\n"
            line += f"\t\t</message>\n"

            # Create child for tooltip
            line += f"\t\t<message>\n"
            line += f"\t\t\t<source>tooltip_{py_dlg['source'].rstrip()}</source>\n"
            if py_dlg[key_lbl] is None:
                py_dlg[key_tooltip] = py_dlg['lb_enen']
            line += f"\t\t\t<translation>{py_dlg[key_tooltip]}</translation>\n"
            line += f"\t\t</message>\n"


            # select dialog_name, source, lb_enen, lb_eses, tt_eses from i18n.pydialog;
        line = '</TS>\n\n'
        ts_file.write(line)
        ts_file.close()
        del ts_file
        lrelease_path = self.plugin_dir + os.sep + 'resources' + os.sep +'lrelease.exe'
        s = subprocess.call([lrelease_path, ts_path], shell=False)
        utils_giswater.setWidgetText(self.dlg_qm, 'lbl_info', 'Translation successful')


    def create_files_db_message(self):
        print("TEST")
    def get_rows(self, sql, commit=True):
        """ Get multiple rows from selected query """

        self.last_error = None
        rows = None
        try:
            self.cursor.execute(sql)
            rows = self.cursor.fetchall()
            if commit:
                self.commit()
        except Exception as e:
            self.last_error = e
            if commit:
                self.rollback()
        finally:
            return rows


    def commit(self):
        """ Commit current database transaction """
        self.conn.commit()

    def rollback(self):
        """ Rollback current database transaction """
        self.conn.rollback()

