from __future__ import absolute_import

from ..plot_object import PlotObject
from ..properties import HasProps
from ..properties import Any, Int, String, Instance, List, Dict, Either

class DataSource(PlotObject):
    """ A base class for data source types. ``DataSource`` is
    not generally useful to instantiate on its own.

    """

    column_names = List(String, help="""
    An list of names for all the columns in this DataSource.
    """)

    selected = List(Int, help="""
    A list of selected indices on this DataSource.
    """)

    def columns(self, *columns):
        """ Returns a ColumnsRef object for a column or set of columns
        on this data source.

        Args:
            *columns

        Returns:
            ColumnsRef

        """
        return ColumnsRef(source=self, columns=list(columns))

class ColumnsRef(HasProps):
    """ A utility object to allow referring to a collection of columns
    from a specified data source, all together.

    """

    source = Instance(DataSource, help="""
    A data source to reference.
    """)

    columns = List(String, help="""
    A list of column names to reference from ``source``.
    """)

class ColumnDataSource(DataSource):
    """ Maps names of columns to sequences or arrays.

    If the ColumnDataSource initializer is called with a single
    argument that is a dict, that argument is used as the value for
    the "data" attribute. For example::

        ColumnDataSource(mydict) # same as ColumnDataSource(data=mydict)

    .. note::
        There is an implicit assumption that all the columns in a
        a given ColumnDataSource have the same length.

    """

    data = Dict(String, Any, help="""
    Mapping of column names to sequences of data. The data can be, e.g,
    Python lists or tuples, NumPy arrays, etc.
    """)

    def __init__(self, *args, **kw):
        """ If called with a single argument that is a dict, treat
        that implicitly as the "data" attribute.
        """
        if len(args) == 1 and "data" not in kw:
            kw["data"] = args[0]
        # TODO (bev) invalid to pass args and "data", check and raise exception
        raw_data = kw.pop("data", {})
        if not isinstance(raw_data, dict):
            import pandas as pd
            if isinstance(raw_data, pd.DataFrame):
                raw_data = self.from_df(raw_data)
            else:
                raise ValueError("expected a dict or pandas.DataFrame, got %s" % raw_data)
        for name, data in raw_data.items():
            self.add(data, name)
        super(ColumnDataSource, self).__init__(**kw)

    # TODO: (bev) why not just return a ColumnDataSource?
    @classmethod
    def from_df(cls, data):
        """ Create a ``dict`` of columns from a Pandas DataFrame,
        suitable for creating a ColumnDataSource.

        Args:
            data (DataFrame) : data to convert

        Returns:
            dict(str, list)

        """
        index = data.index
        new_data = {}
        for colname in data:
            new_data[colname] = data[colname].tolist()
        if index.name:
            new_data[index.name] = index.tolist()
        elif index.names and not all([x is None for x in index.names]):
            new_data["_".join(index.names)] = index.tolist()
        else:
            new_data["index"] = index.tolist()
        return new_data

    def to_df(self):
        """ Convert this data source to pandas dataframe.

        If ``column_names`` is set, use those. Otherwise let Pandas
        infer the column names. The ``column_names`` property can be
        used both to order and filter the columns.

        Returns:
            DataFrame

        """
        import pandas as pd
        if self.column_names:
            return pd.DataFrame(self.data, columns=self.column_names)
        else:
            return pd.DataFrame(self.data)

    def add(self, data, name=None):
        """ Appends a new column of data to the data source.

        Args:
            data (seq) : new data to add
            name (str, optional) : column name to use.
                If not supplied, generate a name go the form "Series ####"

        Returns:
            str:  the column name used

        """
        if name is None:
            n = len(self.data)
            while "Series %d"%n in self.data:
                n += 1
            name = "Series %d"%n
        self.column_names.append(name)
        self.data[name] = data
        return name

    def remove(self, name):
        """ Remove a column of data.

        Args:
            name (str) : name of the column to remove

        Returns:
            None

        .. note::
            If the column name does not exist, a warning is issued.

        """
        try:
            self.column_names.remove(name)
            del self.data[name]
        except (ValueError, KeyError):
            import warnings
            warnings.warn("Unable to find column '%s' in data source" % name)

    def push_notebook(self):
        """ Update date for a plot in the IPthon notebook in place.

        This function can be be used to update data in plot data sources
        in the IPython notebook, without having to use the Bokeh server.

        Returns:
            None

        .. warning::
            The current implementation leaks memory in the IPython notebook,
            due to accumulating JS code. This function typically works well
            with light UI interactions, but should not be used for continuously
            updating data. See :bokeh-issue:`1732` for more details and to
            track progress on potential fixes.

        """
        from IPython.core import display
        from bokeh.protocol import serialize_json
        id = self.ref['id']
        model = self.ref['type']
        json = serialize_json(self.vm_serialize())
        js = """
            var ds = Bokeh.Collections('{model}').get('{id}');
            var data = {json};
            ds.set(data);
        """.format(model=model, id=id, json=json)
        display.display_javascript(js, raw=True)

class ServerDataSource(DataSource):
    """ A data source that referes to data located on a Bokeh server.

    The data from the server is loaded on-demand by the client.

    """

    data_url = String(help="""
    The URL to the Bokeh server endpoint for the data.
    """)

    owner_username = String(help="""
    A username to use for authentication when Bokeh server is operating
    in multi-user mode.
    """)

    data = Dict(String, Any, help="""
    Additional data to include directly in this data source object. The
    columns provided here are merged with those from the Bokeh server.
    """)

    # Paramters of data transformation operations
    # The 'Any' is used to pass primtives around.
    # TODO: (jc) Find/create a property type for 'any primitive/atomic value'
    transform = Dict(String,Either(Instance(PlotObject), Any), help="""
    Paramters of the data transformation operations.

    The associated valuse is minimally a tag that says which downsample routine
    to use.  For some downsamplers, parameters are passed this way too.
    """)