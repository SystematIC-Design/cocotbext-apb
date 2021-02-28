# cocotbext-apb

The AMBA APB extension for CocoTB consists of four components:

 - APB Transaction
 - APB Master
 - APB Slave
 - APB Monitor


## Setup

To install the extension navigate to extensions root folder and use the standard Python install procedure.

_Note: this should be performed with the Python Virtual Environment active_

```bash
cd path/to/cocotbext-apb
python setup.py install
```

To use the extension within a test definition import the extensions using:

```python
import cocotbext.apb as apb
```

## APB Transaction

The APB Transaction object contains the complete information about the APB transfer.

### Read

To create a read transaction the following syntax can be used:

_Note: When no data is provided to the object a READ transaction is created_

```python
transaction = apb.APBTransaction(address = 0x00000000)
```

This creates the following transaction:

| Field      | Value      |
| :--------- | :--------- |
| Address:   | 0x00000000 |
| Direction: | READ       |
| Data:      | 0x........ |


### Write

To create a write transaction the following syntax can be used:

_Note: When data is provided to the object a WRITE transaction is created_

```python
transaction = apb.APBTransaction(address = 0x00000000,
                                 data    = 0x12345678)
```

This creates the following transaction:

| Field      | Value      |
| :--------- | :--------- |
| Address:   | 0x00000000 |
| Direction: | WRITE      |
| Data:      | 0x12345678 |


### Full Set of Keywords

The transaction can be provided a number of keywords to define the transaction, these are:

| Keyword         | Default               | Description                          |
| :-------------- | :-------------------- | :----------------------------------- |
| `address`       |                       | Memory mapped address of transaction |
| `data`          | None                  | Data to be exchanged                 |
| `direction`     | None                  | Direction of data                    |
| `strobe`        | [True,True,True,True] | Which byte lanes are enabled         |
| `error`         | None                  | Has the transaction ended in error   |
| `bus_width`     | 32                    | The number of data bits in the bus   |
| `address_width` | 12                    | The address size                     |


### Creating Randomised Transaction

Once a transaction has been created it can be randomised by calling the function shown below:

```python
transaction.post_randomize()
```

This will create random values for the fields.

_Note: The address will be generated based on the `address_width` setting so this should be set to the appropriate value_


### Viewing a Transaction

To view a transaction simply call it's print function:

```python
transaction.print()
```

Which will print all the transaction paramters:

```
# ------------------------------------------------------------------------------------------------------------------------
# APB Transaction - Started at 3400 ns
# 
#   Address:   0x00000000
#   Direction: READ
#   Data:      0x12345678 
# ------------------------------------------------------------------------------------------------------------------------
```

Note that if the transaction has occurred the simulation time is displayed within the title information. If the transaction has not been initiated yet the this section will read `Has not occurred yet`.


### Comparing Transactions

Equivalence checking is built into the transaction object so two transactions can be compared simply using:

```
transaction_expected == transaction_received
```

_Note that the start time of the transaction is NOT compared_


## APB Monitor

The APB monitor can be used to monitor the activity on an APB bus and extract the information to form an APB transaction.

### Create Monitor

To create a monitor:

```python
monitor = apb.APBMonitor(dut, "APB", dut.APB_PCLK)
```

The `dut` is the standard CocoTB DUT handler. The `APB` string defines the signal name prefix used to find the bus. `dut.APB_HCLK` defines the clock for the bus.

The signal names used are listed below:

 - `PSEL`
 - `PWRITE`
 - `PENABLE`
 - `PADDR`
 - `PWDATA`
 - `PRDATA`
 - `PREADY`

These are optional signals:

 - `PSLVERR`
 - `PSTRB`


There are other ways to connect signals in packed structures or of arbitrary names, this is explored in the section at the end.

### Define a Callback

The monitor constantly observes the bus and extracts transactions. When a transaction is complete a transaction object is formed and a callback is triggered which performs some function with the transaction.

To create a simple call back which prints the received transaction:

```python
def transaction_received(transaction):
    transaction.print()
master_monitor.add_callback(transaction_received)
```

However, the callback can be much more complicated to perform functions such as scoreboarding or collect coverage.


## APB Master

The APB master driver can initiate APB transaction on the bus to perform read/write operations to slaves.

### Create a Master

To create a master:

```python
master  = ahb.AHBMasterDriver(dut, "APB", dut.APB_PCLK)
```

The `dut` is the standard CocoTB DUT handler. The `APB` string defines the signal name prefix used to find the bus. `dut.APB_PCLK` defines the clock for the bus.

The signal names used are listed below:

 - `PSEL`
 - `PWRITE`
 - `PENABLE`
 - `PADDR`
 - `PWDATA`
 - `PRDATA`
 - `PREADY`

These are optional signals:

 - `PSLVERR`
 - `PSTRB`

There are other ways to connect signals in packed structures or of arbitrary names, this is explored in the section at the end.

### Initiate Transactions

To initiate a transaction simply pass that transaction to the master's `send` function:

```python
await master.send(transaction)
```

The master can operate in a buffered manner. It has an internal transaction buffer which can dynamically be appended to create successive transactions automatically.

Multiple calls to the `send` function loads the buffer, this buffer will be processed in the following clock cycles. For example this code loads four transaction which are performed over the following eight clock cycles (the clock cycle wait does not have to be 'dead time' as in this example - other useful functions can run in parallel):

```python
await master.send(transaction0)     # load SINGLE transaction 0
await master.send(transaction1)     # load SINGLE transaction 1
await master.send(transaction2)     # load SINGLE transaction 2
await master.send(transaction3)     # load SINGLE transaction 3
await ClockCycles(dut.PHB_PCLK, 8)  # transaction occur here
# master buffer empty all transaction complete
```


## APB Slave

The APB slave can respond to read/write requests by a master and update it's internal register definition accordingly.

### Create a Slave

To create a master:

```python
slave_registers = [_ for _ in range(32)]
slave_driver  = apb.APBSlaveDriver(dut, "AHB", dut.APB_PCLK, registers=slave_registers)
```

The `dut` is the standard CocoTB DUT handler. The `APB` string defines the signal name prefix used to find the bus. `dut.APB_PCLK` defines the clock for the bus. A register space should be created as a list of integers - this can be set all zeros or other values. During read and write operations the slave will expose this list to the AHB bus as a slave device.

The signal names used are listed below:

 - `PSEL`
 - `PWRITE`
 - `PENABLE`
 - `PADDR`
 - `PWDATA`
 - `PRDATA`
 - `PREADY`

These are optional signals:

 - `PSLVERR`
 - `PSTRB`

There are other ways to connect signals in packed structures or of arbitrary names, this is explored in the section at the end.


### Transactions

The slave is currently very passive, the object allows reading and writing to the defined registers. There are no other functions to directly interact with the slave.


### Random Flow Control

The slave has the ability to randomly deassert the `PREADY` signal to create wait states or assert `PSLVERR` to indicate a failed transaction.

To enable these options the two keywords `random_ready_probability` and `random_error_probability` can be passed to the object when it's created. The values must be between 0 and 1, 0 causes the event to never occur, 1 causes the event to always occur. By default these values are set to 0.


## Signal Mapping

The simplest form of signal mapping occurs when the RTL signal names match those presented above with a prefix. For example the address signal is called `APB_PADDR`in which case the bus name `APB` can be provided and the signal names ie. `PADDR` are appended to create `APB_PADDR`.

However, there are cases where this is not true, the following sections will show how to work around this.


### SystemVerilog Packed Structs

Packed structs in SystemVerilog can be used to group together signals in buses. To work with these the syntax below can be used:

```python
master_driver  = apb.APBMasterDriver(dut, "apb_bus", dut.APB_PCLK, pkg=True)
```

The object will then map the signals, for example the `PADDR` signal will be mapped to `apb_bus_h2d.paddr` and the `PREADY` signal will be mapped to `apb_bus_d2h.pready`.


### Explicit Mapping

In some cases it's required to explicitly map signal names. This can be performed by creating a dictionary with the mapping, for example:

```python
signals = {'PADDR'      :   'address_signal',
           'PWDATA'     :   'write_data_signal',
           ...
           'PREADY'     :   'slave_ready_signal'}
```

This can then be passed to the driver/monitor:

```python
master_driver  = apb.APBMasterDriver(dut, "alternate_names", dut.APB_PCLK, signals=signals)
```

If the name is provided (`alternate_names` in this case) it will prepended as a bus name, ie. `alternate_names_address_signal`. If it is set to `None` no prefix will be made.