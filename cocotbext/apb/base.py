# MIT License

# Copyright (c) 2021 SystematIC Design BV

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
 
"""
APB Transaction and Agent
(Driver + Monitor)
"""

from collections import deque
import random

import cocotb
from cocotb.triggers import RisingEdge, ReadOnly
from cocotb.binary import BinaryValue
from cocotb_bus.drivers import BusDriver
from cocotb_bus.monitors import BusMonitor
from cocotb.result import ReturnValue
from cocotb.decorators import coroutine

from cocotb_coverage.crv import Randomized


# define the PWRITE mapping
pwrite = [  'READ',
            'WRITE'   ]



class APBTransaction(Randomized):
    """
        APB Transaction Class

        Defines the transaction in terms of the fields
    """

    def __init__(self, address, data=None, direction=None, strobe=[True,True,True,True],
                        error=None, bus_width=32, address_width=12):
        Randomized.__init__(self)

        # check input values
        assert direction in [None, 'READ', 'WRITE'], "The direction must be either: None, 'READ', 'WRITE'"

        # select based on read/write operation
        if data != None:
            if direction:
                self.direction  = direction
            else:
                self.direction  = 'WRITE'
            self.data       = data

        else:
            self.direction  = 'READ'
            self.data       = None

        # save the straight through parameters
        self.address   = address
        self.bus_width = bus_width
        self.address_width = address_width
        self.strobe = strobe

        # store the error setting
        if error != None:
            self.error        = error
        else:
            self.error        = False

        # store time of the transaction
        self.start_time = None


    def post_randomize(self):
        '''
            Generate a randomized transaction
        '''

        # select a random direction
        self.direction = ['READ','WRITE'][random.randint(0,1)]

        # select the transaction length
        self.address = random.randint(0,2**(self.address_width-2))*4

        # if we're writing generate the data
        if self.direction == 'WRITE':
            self.data = random.randint(0,self.bus_width)

        # create random strobe data
        for i in range(4):
            self.strobe[i] = bool(random.randint(0,1))


    def print(self):
        '''
            Print a transaction information in a nice readable format
        '''

        print('-'*120)
        print('APB Transaction - ', end='')
        if self.start_time:
            print('Started at %d ns' % self.start_time)
        else:
            print('Has not occurred yet')
        print('')

        print('  Address:   0x%08X' % self.address)
        print('  Direction: %s' % self.direction)
        print('  Data:      ', end='')

        if self.data != None:
            print('0x%0*X ' % (int(self.bus_width/4),self.data))
        else:
            print('NO DATA YET!')

        if self.error:
            print('  TRANSACTION ENDED IN ERROR!')
            print('')
        print('-'*120)

    def convert2string(self):
        """
        Returns a string - used by UVM.
        """
        return "APB: address: %s, direction: %s, data: %s, strobe: %s" % (
            hex(self.address), self.direction, hex(self.data), hex(self._strobe()) )

    #overload (not)equlity operators - just compare mosi and miso data match
    def __ne__(self, other):
        return NotImplemented

    def __eq__(self, other):

        # compare each field
        fail = False
        fail = fail or not (self.address == other.address)
        fail = fail or not (self.direction == other.direction)
        fail = fail or not (self.data == other.data)

        # return response
        return not fail

    def _strobe(self):
        """
        Return an integer representation of the byte strobes.
        """
        try:
            return int(''.join([ '1' if x else '0' for x in self.strobe ]), 2)
        except ValueError as e:
            print(self.strobe)
            raise e

    def __repr__(self):
        return self.convert2string()


class APBMonitor(BusMonitor):
    """
        APB Master Monitor

        Observes the bust to monitor all transactions and provide callbacks
        with the observed data
    """

    def __init__(self, entity, name, clock, pkg=False, signals=None, bus_width=32, **kwargs):

        # has the signals been explicitely defined?
        if signals:
            self._signals = signals

        else:

            # a SystemVerilog package is used
            if pkg:
                self._signals = {}
                for signal_name in ['psel', 'pwrite', 'penable', 'paddr', 'pwdata', 'pstrb']:
                    self._signals[signal_name.upper()] = name + '_h2d_i.' + signal_name

                for signal_name in ['prdata', 'pready', 'pslverr']:
                    self._signals[signal_name.upper()] = name + '_d2h_o.' + signal_name
                name = None

            # just use the default APB names
            else:
                self._signals = [
                    "PSEL",
                    "PWRITE",
                    "PENABLE",
                    "PADDR",
                    "PWDATA",
                    "PRDATA",
                    "PREADY"]

                self._optional_signals = [
                    "PSLVERR",
                    "PSTRB"]

        BusMonitor.__init__(self, entity, name, clock, **kwargs)
        self.clock = clock
        self.bus_width = bus_width

        # prime the monitor to begin
        self.reset()


    def reset(self):
        '''
            Mimic the reset functon in hardware
        '''

        pass



    async def _monitor_recv(self):
        '''
            Keep watching the bus until the peripheral is signalled as:
                Selected
                Enabled
                Ready

            Then simply sample the address, data and direction
        '''

        await RisingEdge(self.clock)
        while True:

            # both slave and master are ready for transfer
            if self.bus.PSEL.value.integer and self.bus.PENABLE.value.integer and self.bus.PREADY.value.integer:

                # retrieve the data from the bus
                address     = self.bus.PADDR.value.integer
                direction   = pwrite[self.bus.PWRITE.value.integer]

                # are we reading or writing?
                if direction == 'READ':
                    data = self.bus.PRDATA.value.integer
                else:
                    data = self.bus.PWDATA.value.integer

                # store the transaction object
                transaction = APBTransaction(   address     = address,
                                                data        = data,
                                                direction   = direction)
                transaction.start_time = cocotb.utils.get_sim_time('ns')

                # find out if there's an error from the slave
                if hasattr(bus,'PSLVERR') and self.bus.PSLVERR.value.integer:
                    transaction.error = True

                # signal to the callback
                self._recv(transaction)

            # begin next cycle
            await RisingEdge(self.clock)



class APBMasterDriver(BusDriver):
    """
        APB Master Driver

        Drives data onto the APB bus to setup for read/write to slave devices.
    """

    def __init__(self, entity, name, clock, pkg=False, signals=None, **kwargs):

        # has the signals been explicitely defined?
        if signals:
            self._signals = signals

        else:

            # a SystemVerilog package is used
            if pkg:
                self._signals = {}
                for signal_name in ['psel', 'pwrite', 'penable', 'paddr', 'pwdata', 'pstrb']:
                    self._signals[signal_name.upper()] = name + '_h2d_i.' + signal_name

                for signal_name in ['prdata', 'pready', 'pslverr']:
                    self._signals[signal_name.upper()] = name + '_d2h_o.' + signal_name
                name = None


            # just use the default APB names
            else:
                self._signals = [
                    "PSEL",
                    "PWRITE",
                    "PENABLE",
                    "PADDR",
                    "PWDATA",
                    "PRDATA",
                    "PREADY"]

                self._optional_signals = [
                    "PSLVERR",
                    "PSTRB"]


        # inheret the bus driver
        BusDriver.__init__(self, entity, name, clock, bus_separator='.', **kwargs)
        self.clock = clock

        # initialise all outputs to zero
        self.bus.PADDR.setimmediatevalue(0)
        self.bus.PWRITE.setimmediatevalue(0)
        self.bus.PSEL.setimmediatevalue(0)
        self.bus.PENABLE.setimmediatevalue(0)
        self.bus.PWDATA.setimmediatevalue(0)
        self.bus.PSTRB.setimmediatevalue(0)

        self.reset()


    def reset(self):
        '''
            Mimic the reset function in hardware
        '''

        # initialise the transmit queue
        self.transmit_queue = deque()
        self.transmit_coroutine = 0


    async def busy_send(self, transaction):
        '''
            Provide a send method that waits for the transaction to complete.
        '''
        await self.send(transaction)
        while (self.transfer_busy):
            await RisingEdge(self.clock)


    async def _driver_send(self, transaction, sync=True, hold=False, **kwargs):
        '''
            Append a new transaction to be transmitted
        '''

        # add new transaction
        self.transmit_queue.append(transaction)

        # launch new transmit pipeline coroutine if aren't holding for and the
        #   the coroutine isn't already running.
        #   If it is running it will just collect the transactions in the
        #   queue once it gets to them.
        if not hold:
            if not self.transmit_coroutine:
                self.transmit_coroutine = cocotb.fork(self._transmit_pipeline())


    async def _transmit_pipeline(self):
        '''
            Maintain a parallel operation transmitting all the items
            in the pipline
        '''

        # default values
        transaction_remaining = 0
        state = 'SETUP'
        self.transfer_busy = True

        # while there's data in the queue keep transmitting
        while len(self.transmit_queue) > 0 or state != 'IDLE':

            if state == 'SETUP':

                # get a new transaction from the queue
                current_transaction = self.transmit_queue.popleft()
                current_transaction.start_time = cocotb.utils.get_sim_time('ns')

                # assign values in the control phase
                self.bus.PSEL.value = 1
                self.bus.PADDR.value = current_transaction.address
                self.bus.PWRITE.value = pwrite.index(current_transaction.direction)

                # create the PSTRB signal
                pstrb_int = 0
                for i, pstrb_i in enumerate(current_transaction.strobe):
                    pstrb_int += pstrb_i << i
                self.bus.PSTRB.value = pstrb_int

                # write the data to the bus
                if current_transaction.direction == 'WRITE':
                    self.bus.PWDATA.value = current_transaction.data

                # update state
                state = 'ACCESS'

            elif state == 'ACCESS':

                # tell the slave we're ready for the access phase
                self.bus.PENABLE.value = 1

                state = 'SAMPLE'


            await RisingEdge(self.clock)

            if state == 'SAMPLE':

                # is the slave ready?
                if self.bus.PREADY.value.integer:

                    # check if the slave is asserting an error
                    if hasattr(bus,'PSLVERR') and self.bus.PSLVERR.value.integer:
                        current_transaction.error = True

                    # if this is a read we should sample the data
                    if current_transaction.direction == 'READ':
                        current_transaction.data = self.bus.PRDATA.value.integer

                    # what's the next state?
                    if len(self.transmit_queue) > 0:
                        state = 'SETUP'
                    else:
                        state = 'IDLE'
                    self.bus.PENABLE.value = 0

        # reset the bus signals
        self.bus.PWDATA.value = 0
        self.bus.PWRITE.value = 0
        self.bus.PSEL.value = 0
        self.bus.PENABLE.value = 0

        self.transfer_busy = False



class APBSlaveDriver(BusMonitor):
    """
        APB Slave Driver

        Responds to a masters request for a read/write.
    """


    def __init__(self, entity, name, clock, registers, signals=None, pkg=False,
                    random_ready_probability=0, random_error_probability=0, **kwargs):

        # has the signals been explicitely defined?
        if signals:
            self._signals = signals

        else:

            # a SystemVerilog package is used
            if pkg:
                self._signals = {}
                for signal_name in ['psel', 'pwrite', 'penable', 'paddr', 'pwdata', 'pstrb']:
                    self._signals[signal_name.upper()] = name + '_h2d.' + signal_name

                for signal_name in ['prdata', 'pready', 'pslverr']:
                    self._signals[signal_name.upper()] = name + '_d2h.' + signal_name
                name = None


            # just use the default APB names
            else:
                self._signals = [
                    "PSEL",
                    "PWRITE",
                    "PENABLE",
                    "PADDR",
                    "PWDATA",
                    "PRDATA",
                    "PREADY"]

                self._optional_signals = [
                    "PSLVERR",
                    "PSTRB"]

        BusMonitor.__init__(self, entity, name, clock, **kwargs)
        self.clock = clock

        # initialise all outputs to zero
        self.bus.PRDATA.setimmediatevalue(0)
        self.bus.PREADY.setimmediatevalue(0)
        if hasattr(bus,'PSLVERR'):
            self.bus.PSLVERR.setimmediatevalue(0)

        # store the default registers value
        self.registers_init = registers

        # setting for the probability of PREADY delay
        self.random_ready_probability = random_ready_probability
        self.random_error_probability = random_error_probability

        self.reset()



    def reset(self):
        '''
            Mimic the reset function in hardware
        '''

        # initialise the registers value
        self.registers = self.registers_init



    async def _monitor_recv(self):
        '''
            Monitor the bus and respond to transactions
        '''

        await RisingEdge(self.clock)

        # default to ready
        self.bus.PREADY.value = 1
        state = 'IDLE'

        while True:


            # get the register word index
            address = self.bus.PADDR.value.integer
            word_index = int( (address % (2**self.address_bits-1) ) / 4 )


            if state == 'IDLE':

                # we're starting a transaction
                if self.bus.PSEL.value.integer:

                    # store the start time of the transaction
                    start_time = cocotb.utils.get_sim_time('ns')

                    # insert a wait state?
                    if random.random() < self.random_ready_probability:
                        self.bus.PREADY.value = 0
                        state = 'IDLE'
                    else:

                        # error in transaction?
                        if random.random() < self.random_error_probability:
                            self.bus.PRDATA.value = 0x00000000
                            if hasattr(bus,'PSLVERR'):
                                self.bus.PSLVERR.value = 1
                        else:

                            # is the address within bounds?
                            if word_index-1 > len(self.registers):
                                self.entity._log.info("APB slave given invalid address. Providing ERROR response.")
                                if hasattr(bus,'PSLVERR'):
                                    self.bus.PSLVERR.value = 1

                            else:
                                # place data on the bus
                                if pwrite[self.bus.PWRITE.value.integer] == 'READ':
                                    self.bus.PRDATA.value = self.registers[word_index]


                        self.bus.PREADY.value = 1
                        state = 'ACCESS'

            # sample the data
            elif state == 'ACCESS':

                # is the address within bounds?
                if word_index-1 > len(self.registers):

                    # sample data from the bus
                    if pwrite[self.bus.PWRITE.value.integer] == 'WRITE':
                        self.registers[word_index] = self.bus.PWDATA.value.integer

                # reset the bus values
                self.bus.PRDATA.value = 0
                self.bus.PREADY.value = 1
                if hasattr(bus,'PSLVERR'):
                    self.bus.PSLVERR.value = 0
                state = 'IDLE'

            await RisingEdge(self.clock)
