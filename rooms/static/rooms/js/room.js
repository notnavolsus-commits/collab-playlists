document.addEventListener('DOMContentLoaded', function() {

    const slug = window.location.pathname.split('/').filter(p => p).pop();

    const socket = new WebSocket(`ws://127.0.0.1:8000/ws/rooms/${slug}/`);

    socket.onopen = function(event) {
        console.log('Websocket подключён!');
    };

    socket.onerror = function(error) {
        console.log('Ошибка:', error);
    };

    socket.onclose = function(event) {
        console.log('Соединение закрыто');
    };

    socket.onmessage = function(event) {
        const data = JSON.parse(event.data);
        let room_track_id = data['room_track_id'];
        let new_votes_count = data['new_votes_count'];
        let vote_counter = document.querySelector(`#votes-${room_track_id}`)
        if (vote_counter) {
        vote_counter.innerText = `${new_votes_count}`;
        }
    };

    const buttons = document.querySelectorAll('button[data-track-id]');

    for (const button of buttons) {
        button.addEventListener('click', () => {
            const trackId = button.dataset.trackId
            socket.send(JSON.stringify({action: 'vote', room_track_id: trackId}));
            console.log('Голос отправлен', trackId)
    });}
});
