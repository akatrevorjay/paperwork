#    Paperwork - Using OCR to grep dead trees the easy way
#    Copyright (C) 2012  Jerome Flesch
#
#    Paperwork is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    Paperwork is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with Paperwork.  If not, see <http://www.gnu.org/licenses/>.

import codecs
import datetime
import gettext
import logging
import os
import os.path
import time

from paperwork.backend.common.page import BasicPage
from paperwork.backend.labels import Label
from paperwork.util import dummy_progress_cb
from paperwork.util import rm_rf


_ = gettext.gettext
logger = logging.getLogger(__name__)


class BasicDoc(object):
    LABEL_FILE = "labels"
    DOCNAME_FORMAT = "%Y%m%d_%H%M_%S"
    EXTRA_TEXT_FILE = "extra.txt"

    pages = []
    can_edit = False

    def __init__(self, docpath, docid=None):
        """
        Basic init of common parts of doc.

        Note regarding subclassing: *do not* load the document
        content in __init__(). It would reduce in a huge performance loose
        and thread-safety issues. Load the content on-the-fly when requested.
        """
        if docid is None:
            self.__docid = time.strftime(self.DOCNAME_FORMAT)
            self.path = os.path.join(docpath, self.__docid)
        else:
            self.__docid = docid
            self.path = docpath
        self.__cache = {}

    def drop_cache(self):
        self.__cache = {}

    def __str__(self):
        return self.__docid

    def __get_last_mod(self):
        raise NotImplementedError()

    last_mod = property(__get_last_mod)

    def __get_nb_pages(self):
        if not 'nb_pages' in self.__cache:
            self.__cache['nb_pages'] = self._get_nb_pages()
        return self.__cache['nb_pages']

    nb_pages = property(__get_nb_pages)

    def redo_ocr(self, langs, callback=dummy_progress_cb):
        """
        Run the OCR again on all the pages of the document

        Arguments
        """
        nb_pages = self.nb_pages
        for i in range(0, nb_pages):
            callback(i, nb_pages, BasicPage.SCAN_STEP_OCR, self)
            page = self.pages[i]
            page.redo_ocr(langs)

    def print_page_cb(self, print_op, print_context, page_nb):
        raise NotImplementedError()

    def __get_doctype(self):
        raise NotImplementedError()

    doctype = property(__get_doctype)

    def __get_keywords(self):
        """
        Yield all the keywords contained in the document.
        """
        for page in self.pages:
            for keyword in page.keywords:
                yield(keyword)

    keywords = property(__get_keywords)

    def destroy(self):
        """
        Delete the document. The *whole* document. There will be no survivors.
        """
        logger.info("Destroying doc: %s" % self.path)
        rm_rf(self.path)
        logger.info("Done")
        self.drop_cache()

    def add_label(self, label):
        """
        Add a label on the document.
        """
        if label in self.labels:
            return
        with codecs.open(os.path.join(self.path, self.LABEL_FILE), 'a',
                         encoding='utf-8') as file_desc:
            file_desc.write("%s,%s\n" % (label.name, label.get_color_str()))
        self.drop_cache()

    def remove_label(self, to_remove):
        """
        Remove a label from the document. (-> rewrite the label file)
        """
        if not to_remove in self.labels:
            return
        labels = self.labels
        labels.remove(to_remove)
        with codecs.open(os.path.join(self.path, self.LABEL_FILE), 'w',
                         encoding='utf-8') as file_desc:
            for label in labels:
                file_desc.write("%s,%s\n" % (label.name,
                                             label.get_color_str()))
        self.drop_cache()

    def __get_labels(self):
        """
        Read the label file of the documents and extract all the labels

        Returns:
            An array of labels.Label objects
        """
        if not 'labels' in self.__cache:
            labels = []
            try:
                with codecs.open(os.path.join(self.path, self.LABEL_FILE), 'r',
                                 encoding='utf-8') as file_desc:
                    for line in file_desc.readlines():
                        line = line.strip()
                        (label_name, label_color) = line.split(",")
                        labels.append(Label(name=label_name,
                                            color=label_color))
            except IOError:
                pass
            self.__cache['labels'] = labels
        return self.__cache['labels']

    labels = property(__get_labels)

    def update_label(self, old_label, new_label):
        """
        Update a label

        Will go on each document, and replace 'old_label' by 'new_label'
        """
        logger.info("%s : Updating label ([%s] -> [%s])"
               % (str(self), str(old_label), str(new_label)))
        labels = self.labels
        try:
            labels.remove(old_label)
        except ValueError:
            # this document doesn't have this label
            return
        labels.append(new_label)
        with codecs.open(os.path.join(self.path, self.LABEL_FILE), 'w',
                         encoding='utf-8') as file_desc:
            for label in labels:
                file_desc.write("%s,%s\n" % (label.name,
                                             label.get_color_str()))
        self.drop_cache()

    @staticmethod
    def get_export_formats():
        raise NotImplementedError()

    def build_exporter(self, file_format='pdf'):
        """
        Returns:
            Returned object must implement the following methods/attributes:
            .can_change_quality = (True|False)
            .set_quality(quality_pourcent)
            .estimate_size() : returns the size in bytes
            .get_img() : returns a Pillow Image
            .get_mime_type()
            .get_file_extensions()
            .save(file_path)
        """
        raise NotImplementedError()

    def __doc_cmp(self, other):
        """
        Comparison function. Can be used to sort docs alphabetically.
        """
        if other is None:
            return -1
        return cmp(self.__docid, other.__docid)

    def __lt__(self, other):
        return self.__doc_cmp(other) < 0

    def __gt__(self, other):
        return self.__doc_cmp(other) > 0

    def __eq__(self, other):
        return self.__doc_cmp(other) == 0

    def __le__(self, other):
        return self.__doc_cmp(other) <= 0

    def __ge__(self, other):
        return self.__doc_cmp(other) >= 0

    def __ne__(self, other):
        return self.__doc_cmp(other) != 0

    def __hash__(self):
        return hash(self.__docid)

    def __is_new(self):
        try:
            os.stat(self.path)
            return False
        except OSError:
            # this document doesn't exist yet
            return True

    is_new = property(__is_new)

    def __get_name(self):
        """
        Returns the localized name of the document (see l10n)
        """
        if self.is_new:
            return _("New document")
        try:
            split = self.__docid.split("_")
            short_docid = "_".join(split[:3])
            datetime_obj = datetime.datetime.strptime(
                short_docid, self.DOCNAME_FORMAT)
            final = datetime_obj.strftime("%x")
            return final
        except Exception, exc:
            logger.error("Unable to parse document id [%s]: %s"
                    % (self.docid, exc))
            return self.docid

    name = property(__get_name)

    def __get_docid(self):
        return self.__docid

    def __set_docid(self, new_base_docid):
        workdir = os.path.dirname(self.path)
        new_docid = new_base_docid
        new_docpath = os.path.join(workdir, new_docid)
        idx = 0

        while os.path.exists(new_docpath):
            idx += 1
            new_docid = new_base_docid + ("_%02d" % idx)
            new_docpath = os.path.join(workdir, new_docid)

        self.__docid = new_docid
        if self.path != new_docpath:
            logger.info("Changing docid: %s -> %s" % (self.path, new_docpath))
            os.rename(self.path, new_docpath)
            self.path = new_docpath

    docid = property(__get_docid, __set_docid)

    def __get_date(self):
        try:
            split = self.__docid.split("_")[0]
            return (int(split[0:4]),
                    int(split[4:6]),
                    int(split[6:8]))
        except (IndexError, ValueError):
            return (1985, 12, 19)

    def __set_date(self, new_date):
        new_id = ("%02d%02d%02d_0000_01"
                  % (new_date[0],
                     new_date[1],
                     new_date[2]))
        self.docid = new_id

    date = property(__get_date, __set_date)

    def __get_extra_text(self):
        extra_txt_file = os.path.join(self.path, self.EXTRA_TEXT_FILE)
        if not os.access(extra_txt_file, os.R_OK):
            return u""
        with codecs.open(extra_txt_file, 'r', encoding='utf-8') as file_desc:
            text = file_desc.read()
            return text

    def __set_extra_text(self, txt):
        extra_txt_file = os.path.join(self.path, self.EXTRA_TEXT_FILE)

        txt = txt.strip()
        if txt == u"":
            os.unlink(extra_txt_file)
        else:
            with codecs.open(extra_txt_file, 'w',
                             encoding='utf-8') as file_desc:
                file_desc.write(txt)

    extra_text = property(__get_extra_text, __set_extra_text)
