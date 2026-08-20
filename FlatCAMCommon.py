############################################################
# FlatCAM: 2D Post-processing for Manufacturing            #
############################################################

def qt_widget_alive(widget):
    """True if ``widget`` is a live Qt object (not a deleted Shiboken wrapper)."""
    if widget is None:
        return False
    try:
        from shiboken6 import isValid
        return bool(isValid(widget))
    except Exception:
        pass
    try:
        widget.objectName()
        return True
    except RuntimeError:
        return False


def park_scroll_widget(scroll_area, new_widget):
    """
    Put ``new_widget`` in ``scroll_area`` without destroying the previous one.

    QScrollArea.setWidget() deletes the current child. Object forms and the
    options pages must survive being swapped out.
    """
    if scroll_area is None or new_widget is None:
        return
    if not qt_widget_alive(new_widget):
        return
    current = scroll_area.widget()
    if current is new_widget:
        return
    taken = scroll_area.takeWidget()
    if taken is not None and taken is not new_widget and qt_widget_alive(taken):
        taken.setParent(None)
        taken.hide()
    scroll_area.setWidget(new_widget)
    new_widget.show()


class LoudDict(dict):
    """
    A Dictionary with a callback for
    item changes.
    """

    def __init__(self, *args, **kwargs):
        dict.__init__(self, *args, **kwargs)
        self.callback = lambda x: None

    def __setitem__(self, key, value):
        """
        Overridden __setitem__ method. Invokes the change callback
        if the item was changed, with key as parameter.
        """
        if key in self and self.__getitem__(key) == value:
            return

        dict.__setitem__(self, key, value)
        self.callback(key)

    def update(self, *args, **kwargs):
        if len(args) > 1:
            raise TypeError("update expected at most 1 arguments, got %d" % len(args))
        other = dict(*args, **kwargs)
        for key in other:
            self[key] = other[key]

    def set_change_callback(self, callback):
        """
        Assigns a function as callback on item change. The callback
        will receive the key of the object that was changed.

        :param callback: Function to call on item change.
        :type callback: func
        :return: None
        """

        self.callback = callback

