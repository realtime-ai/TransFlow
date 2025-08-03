import { useEffect, useState, useCallback, useRef } from 'react';
import { io, Socket } from 'socket.io-client';

interface UseSocketIOOptions {
  autoConnect?: boolean;
  reconnection?: boolean;
  reconnectionAttempts?: number;
  reconnectionDelay?: number;
}

interface UseSocketIOReturn {
  socket: Socket | null;
  isConnected: boolean;
  emit: (event: string, data?: any) => void;
  on: (event: string, handler: (data: any) => void) => void;
  off: (event: string, handler?: (data: any) => void) => void;
  connect: () => void;
  disconnect: () => void;
}

export function useSocketIO(
  url: string,
  options: UseSocketIOOptions = {}
): UseSocketIOReturn {
  const [socket, setSocket] = useState<Socket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const socketRef = useRef<Socket | null>(null);

  useEffect(() => {
    // Only run on client side
    if (typeof window === 'undefined') return;

    const {
      autoConnect = true,
      reconnection = true,
      reconnectionAttempts = 5,
      reconnectionDelay = 3000,
    } = options;

    const newSocket = io(url, {
      autoConnect,
      reconnection,
      reconnectionAttempts,
      reconnectionDelay,
      transports: ['websocket'],
    });

    socketRef.current = newSocket;
    setSocket(newSocket);

    newSocket.on('connect', () => {
      console.log('Socket.IO connected');
      setIsConnected(true);
    });

    newSocket.on('disconnect', () => {
      console.log('Socket.IO disconnected');
      setIsConnected(false);
    });

    newSocket.on('connect_error', (error) => {
      console.error('Socket.IO connection error:', error);
    });

    newSocket.on('error', (error) => {
      console.error('Socket.IO error:', error);
    });

    return () => {
      newSocket.disconnect();
      socketRef.current = null;
    };
  }, [url]);

  const emit = useCallback((event: string, data?: any) => {
    if (typeof window === 'undefined') return;
    if (socketRef.current?.connected) {
      socketRef.current.emit(event, data);
    } else {
      console.warn('Socket.IO is not connected. Cannot emit:', event);
    }
  }, []);

  const on = useCallback((event: string, handler: (data: any) => void) => {
    if (typeof window === 'undefined') return;
    if (socketRef.current) {
      socketRef.current.on(event, handler);
    }
  }, []);

  const off = useCallback((event: string, handler?: (data: any) => void) => {
    if (typeof window === 'undefined') return;
    if (socketRef.current) {
      if (handler) {
        socketRef.current.off(event, handler);
      } else {
        socketRef.current.off(event);
      }
    }
  }, []);

  const connect = useCallback(() => {
    if (typeof window === 'undefined') return;
    if (socketRef.current && !socketRef.current.connected) {
      socketRef.current.connect();
    }
  }, []);

  const disconnect = useCallback(() => {
    if (typeof window === 'undefined') return;
    if (socketRef.current && socketRef.current.connected) {
      socketRef.current.disconnect();
    }
  }, []);

  return {
    socket,
    isConnected,
    emit,
    on,
    off,
    connect,
    disconnect,
  };
}