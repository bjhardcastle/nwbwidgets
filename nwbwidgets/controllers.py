from ipywidgets import widgets, Layout, ValueWidget, link, HBox
from ipywidgets.widgets.widget_description import DescriptionWidget
import numpy as np
from hdmf.common import DynamicTable
from .utils.dynamictable import group_and_sort, infer_categorical_columns
from .utils.pynwb import robust_unique
from typing import Iterable


class RangeController(widgets.HBox, ValueWidget, DescriptionWidget):

    def __init__(self, vmin, vmax, start_value=None, dtype='float', description='time window (s)',
                 orientation='horizontal', **kwargs):

        if orientation not in ('horizontal', 'vertical'):
            ValueError('Unrecognized orientation: {}'.format(orientation))

        self.vmin = vmin
        self.vmax = vmax
        self.start_value = start_value
        self.orientation = orientation
        self.dtype = dtype

        super().__init__()

        self.slider = self.make_range_slider(description=description, **kwargs)

        [link((self.slider, attr), (self, attr)) for attr in ('value', 'description')]

        if self.orientation == 'horizontal':
            self.to_start_button = widgets.Button(description='◀◀', layout=Layout(width='55px'))
            self.backwards_button = widgets.Button(description='◀', layout=Layout(width='40px'))
            self.forward_button = widgets.Button(description='▶', layout=Layout(width='40px'))
            self.to_end_button = widgets.Button(description='▶▶', layout=Layout(width='55px'))
        else:  # vertical
            self.to_end_button = widgets.Button(description='▲▲', layout=Layout(width='50px'))
            self.forward_button = widgets.Button(description='▲', layout=Layout(width='50px'))
            self.backwards_button = widgets.Button(description='▼', layout=Layout(width='50px'))
            self.to_start_button = widgets.Button(description='▼▼', layout=Layout(width='50px'))

        self.to_start_button.on_click(self.move_start)
        self.backwards_button.on_click(self.move_down)
        self.forward_button.on_click(self.move_up)
        self.to_end_button.on_click(self.move_end)

        self.children = self.get_children()

    def get_children(self):
        if self.orientation == 'horizontal':
            return [
                self.slider,
                self.to_start_button,
                self.backwards_button,
                self.forward_button,
                self.to_end_button
            ]
        elif self.orientation == 'vertical':
            return [widgets.VBox([
                self.slider,
                self.to_end_button,
                self.forward_button,
                self.backwards_button,
                self.to_start_button,
            ],
                layout=widgets.Layout(display='flex',
                                      flex_flow='column',
                                      align_items='center')
            )]
        else:
            raise ValueError('Unrecognized orientation: {}'.format(self.orientation))

    def make_range_slider(self, **kwargs):
        """

        Parameters
        ----------
        kwargs: passed into RangeSlider constructor

        Returns
        -------

        """

        slider_kwargs = dict(
            value=self.start_value,
            min=self.vmin,
            max=self.vmax,
            continuous_update=False,
            readout=True,
            style={'description_width': 'initial'},
            orientation=self.orientation
        )

        if self.dtype == 'float':
            slider_kwargs.update(
                readout_format='.1f',
                step=0.1,
                description='time window (s)',
                layout=Layout(width='100%')
            )
            slider_kwargs.update(kwargs)
            return widgets.FloatRangeSlider(**slider_kwargs)
        elif self.dtype == 'int':
            slider_kwargs.update(
                description='unit window',
                layout=Layout(height='100%')
            )
            slider_kwargs.update(kwargs)
            return widgets.IntRangeSlider(**slider_kwargs)
        else:
            raise ValueError('Unrecognized dtype: {}'.format(self.dtype))

    def move_up(self, change):
        value_range = self.value[1] - self.value[0]
        if self.value[1] + value_range < self.vmax:
            self.value = (self.value[0] + value_range, self.value[1] + value_range)
        else:
            self.move_end(change)

    def move_down(self, change):
        value_range = self.value[1] - self.value[0]
        if self.value[0] - value_range > self.vmin:
            self.value = (self.value[0] - value_range, self.value[1] - value_range)
        else:
            self.move_start(change)

    def move_start(self, change):
        value_range = self.value[1] - self.value[0]
        self.value = (self.vmin, self.vmin + value_range)

    def move_end(self, change):
        value_range = self.value[1] - self.value[0]
        self.value = (self.vmax - value_range, self.vmax)


class StartAndDurationController(HBox, ValueWidget, DescriptionWidget):
    """
    Can be used in place of the RangeController.
    """
    def __init__(self, tmax, tmin=0, start_value=None, duration=1., dtype='float', description='window (s)',
                 **kwargs):

        self.tmin = tmin
        self.tmax = tmax
        self.start_value = start_value
        self.dtype = dtype

        self.slider = widgets.FloatSlider(
            value=start_value,
            min=tmin,
            max=tmax,
            step=0.01,
            description=description,
            continuous_update=False,
            orientation='horizontal',
            readout=True,
            readout_format='.2f',
            style={'description_width': 'initial'},
            layout=Layout(width='100%'))

        self.duration = widgets.BoundedFloatText(
            value=duration,
            min=0,
            max=tmax - tmin,
            step=0.1,
            description='duration (s):',
            style={'description_width': 'initial'},
            layout=Layout(max_width='140px')
        )

        super().__init__()
        link((self.slider, 'description'), (self, 'description'))

        self.value = (self.slider.value, self.slider.value + self.duration.value)

        self.forward_button = widgets.Button(description='▶', layout=Layout(width='50px'))
        self.forward_button.on_click(self.move_up)

        self.backwards_button = widgets.Button(description='◀', layout=Layout(width='50px'))
        self.backwards_button.on_click(self.move_down)

        self.children = [self.slider, self.duration, self.backwards_button, self.forward_button]

        self.slider.observe(self.monitor_slider)
        self.duration.observe(self.monitor_duration)

    def monitor_slider(self, change):
        if 'new' in change:
            if isinstance(change['new'], dict):
                if 'value' in change['new']:
                    value = change['new']['value']
                else:
                    return
            else:
                value = change['new']
        if value + self.duration.value > self.tmax:
            self.slider.value = self.tmax - self.duration.value
        else:
            self.value = (value, value + self.duration.value)

    def monitor_duration(self, change):
        if 'new' in change:
            if isinstance(change['new'], dict):
                if 'value' in change['new']:
                    value = change['new']['value']
                    if self.slider.value + value > self.tmax:
                        self.slider.value = self.tmax - value
                    self.value = (self.slider.value, self.slider.value + value)

    def move_up(self, change):
        if self.slider.value + 2 * self.duration.value < self.tmax:
            self.slider.value += self.duration.value
        else:
            self.slider.value = self.tmax - self.duration.value

    def move_down(self, change):
        if self.slider.value - self.duration.value > self.tmin:
            self.slider.value -= self.duration.value
        else:
            self.slider.value = self.tmin


class AbstractGroupAndSortController(widgets.VBox, ValueWidget, DescriptionWidget):
    """
    Defines the abstract type for GroupAndSortController objects. These classes take in a DynamicTable objects
    and broadcast a `value` of the form
    dict(
        order=array-like(uint),
        group_inds=array-like(uint) | None,
        labels=array-like(str) | None
    )
    """
    def __init__(self, dynamic_table: DynamicTable):
        super().__init__()

        self.dynamic_table = dynamic_table
        self.nitems = len(self.dynamic_table.id)

        self.group_vals = None
        self.group_by = None
        self.group_select = None
        self.limit = None
        self.desc = False
        self.order_by = None
        self.order_vals = None


class GroupAndSortController(AbstractGroupAndSortController):
    def __init__(self, dynamic_table: DynamicTable, group_by=None):
        super().__init__(dynamic_table)

        groups = self.get_groups()

        self.limit_bit = widgets.BoundedIntText(value=50, min=0, max=99999, disabled=True,
                                                layout=Layout(max_width='70px'))
        self.limit_bit.observe(self.limit_bit_observer)

        self.limit_cb = widgets.Checkbox(description='limit', style={'description_width': 'initial'}, disabled=True,
                                         indent=False, layout=Layout(max_width='70px'))
        self.limit_cb.observe(self.limit_cb_observer)

        self.order_dd = widgets.Dropdown(options=[None] + list(groups), description='order by',
                                         layout=Layout(max_width='120px'), style={'description_width': 'initial'})
        self.order_dd.observe(self.order_dd_observer)

        self.ascending_dd = widgets.Dropdown(options=['ASC', 'DESC'], disabled=True,
                                             layout=Layout(max_width='70px'))
        self.ascending_dd.observe(self.ascending_dd_observer)

        self.range_controller = RangeController(0, self.nitems, start_value=(0, 32), dtype='int', description='units',
                                                orientation='vertical')
        self.range_controller.observe(self.range_controller_observer)

        self.group_sm = widgets.SelectMultiple(layout=Layout(max_width='100px'), disabled=True, rows=1)
        self.group_sm.observe(self.group_sm_observer)

        if group_by is None:
            self.group_dd = widgets.Dropdown(options=[None] + list(groups), description='group by',
                                             style={'description_width': 'initial'}, layout=Layout(width='90%'))
            self.group_dd.observe(self.group_dd_observer)
        else:
            self.group_dd = None
            self.set_group_by(group_by)

        self.window = self.range_controller.value

        self.value = dict(order=None, group_inds=None, labels=None)

        link((self.range_controller, 'description'), (self, 'description'))

        self.children = self.get_children()

        self.group_and_sort()

        # self.layout = Layout(max_width='250px')

    def get_children(self):
        children = [
            widgets.HBox(children=(self.group_sm, self.range_controller)),
            widgets.HBox(children=(self.limit_cb, self.limit_bit), layout=Layout(max_width='90%')),
            widgets.HBox(children=(self.order_dd, self.ascending_dd), layout=Layout(max_width='90%')),
        ]

        if self.group_dd:
            children.insert(0, self.group_dd)

        return children

    def set_group_by(self, group_by):
        self.limit_cb.disabled = False
        self.group_by = group_by
        self.group_vals = self.get_group_vals(by=group_by)
        self.set_range_max()
        groups = list(np.unique(self.group_vals))
        self.group_sm.options = groups[::-1]
        self.group_sm.value = groups
        self.group_sm.disabled = False
        self.group_sm.rows = min(len(groups), 20)

    def group_dd_observer(self, change):
        """group dropdown observer"""
        if change['name'] == 'value':
            group_by = change['new']
            if group_by in ('None', '', None):
                self.limit_bit.disabled = True
                self.limit_cb.disabled = True
                self.group_vals = None
                self.group_by = None
                self.limit = None
                self.limit_cb.value = False

                self.range_controller.slider.max = self.nitems
            else:
                self.set_group_by(group_by)

            self.group_and_sort()

    def limit_bit_observer(self, change):
        """limit bounded int text observer"""
        if change['name'] == 'value':
            limit = self.limit_bit.value
            self.limit = limit
            self.set_range_max()
            self.group_and_sort()

    def limit_cb_observer(self, change):
        """limit checkbox observer"""
        if change['name'] == 'value':
            if self.limit_cb.value and self.group_by is not None:
                self.limit_bit.disabled = False
                self.limit = self.limit_bit.value
            else:
                self.limit_bit.disabled = True
                self.limit = None
                self.range_controller.slider.max = self.nitems
            self.set_range_max()
            self.group_and_sort()

    def order_dd_observer(self, change):
        """order dropdown observer"""
        if change['name'] == 'value':
            self.order_by = self.order_dd.value

            order_vals = self.get_group_vals(by=self.order_by)
            # convert to ints. This is mainly for handling strings
            _, order_vals = np.unique(order_vals, return_inverse=True)

            if self.desc:  # if descend is on, invert order.
                order_vals *= -1

            self.order_vals = order_vals

            self.ascending_dd.disabled = self.order_dd.value is None
            self.group_and_sort()

    def ascending_dd_observer(self, change):
        """ascending dropdown observer"""
        if change['name'] == 'value':
            if change['new'] == 'ASC':
                self.desc = False
                self.order_vals *= -1
            else:
                self.desc = True
                self.order_vals *= -1
            self.group_and_sort()

    def group_sm_observer(self, change):
        """group SelectMultiple observer"""
        if change['name'] == 'value' and not self.group_sm.disabled:
            self.group_select = change['new']
            self.set_range_max()
            self.group_and_sort()

    def range_controller_observer(self, change):
        self.window = self.range_controller.value
        self.group_and_sort()

    def get_groups(self):
        return infer_categorical_columns(self.dynamic_table)

    def set_range_max(self):
        if self.group_vals is not None:
            # remove nans
            if hasattr(self.group_vals, 'dtype') and self.group_vals.dtype == np.float64:
                group_vals = self.group_vals[~np.isnan(self.group_vals)]
            else:
                group_vals = self.group_vals
            if self.limit is None:
                self.range_controller.slider.max = len(group_vals)
            else:
                self.range_controller.slider.max = sum(min(sum(self.group_vals == x), self.limit)
                                                       for x in np.unique(group_vals))

    def get_group_vals(self, by, units_select=()):
        if by is None:
            return None
        elif by in self.dynamic_table:
            return self.dynamic_table[by][:][units_select]
        else:
            raise ValueError('column {} not in DynamicTable {}'.format(by, self.dynamic_table))

    def get_orderable_cols(self):
        candidate_cols = [x for x in self.units.colnames
                          if not isinstance(self.units[x][0], Iterable) or
                          isinstance(self.units[x][0], str)]
        return [x for x in candidate_cols if len(robust_unique(self.units[x][:])) > 1]

    def group_and_sort(self):
        if not (self.group_vals is None and self.order_vals is None):
            order, group_inds, labels = group_and_sort(self.group_vals, self.group_select, self.order_vals, self.limit,
                                                       self.window)
        else:
            order, group_inds, labels = np.arange(self.window[0], self.window[1], dtype='int'), None, None

        self.value = dict(order=order, group_inds=group_inds, labels=labels)


def make_trial_event_controller(trials):
    trial_events = ['start_time']
    if not np.all(np.isnan(trials['stop_time'].data)):
        trial_events.append('stop_time')
    trial_events += [x.name for x in trials.columns if
                     (('_time' in x.name) and (x.name not in ('start_time', 'stop_time')))]
    trial_event_controller = widgets.Dropdown(options=trial_events,
                                              value='start_time',
                                              description='align to: ')
    return trial_event_controller
