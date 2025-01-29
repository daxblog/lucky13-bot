const express = require('express');
const http = require('http');
const socketIo = require('socket.io');

const app = express();
const server = http.createServer(app);
const io = socketIo(server);

// Verzend een bericht bij verbinding
io.on('connection', (socket) => {
  console.log('New client connected');
  socket.emit('update_balance', { balance: 100 }); // Verzend de beginbalans

  socket.on('disconnect', () => {
    console.log('Client disconnected');
  });
});

app.get('/', (req, res) => {
  res.send('Lucky13 Trading Bot');
});

const PORT = process.env.PORT || 5000;
server.listen(PORT, () => {
  console.log(`Server running on port ${PORT}`);
});
